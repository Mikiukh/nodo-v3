import logging
import os
import re
import threading
import time
from datetime import date, datetime, timedelta
from functools import wraps

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from openai import OpenAI
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from models import (
    db,
    Activity,
    AdminAudit,
    Achievement,
    ChatMessage,
    CompletedMission,
    Course,
    Friend,
    Group,
    Mission,
    Notification,
    Post,
    PostComment,
    PostLike,
    Purchase,
    Report,
    StoreItem,
    User,
    UserAchievement,
)
from security import decode_token, hash_password, make_token, require_auth, verify_password


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------


def normalize_database_url(url: str) -> str:
    if url and url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg://', 1)
    if url and url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+psycopg://', 1)
    return url


IS_PRODUCTION = bool(os.getenv('RENDER') or os.getenv('APP_ENV') == 'production')
DATABASE_URL = normalize_database_url(os.getenv('DATABASE_URL', 'sqlite:///nodo.db'))
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-local-only')
JWT_SECRET = os.getenv('JWT_SECRET', 'dev-secret-local-only')

if IS_PRODUCTION:
    weak_values = {'', 'dev-local-only', 'dev-secret-local-only', 'troque_por_uma_chave_forte', 'troque_por_uma_chave_jwt_forte'}
    if SECRET_KEY in weak_values or len(SECRET_KEY) < 32:
        raise RuntimeError('SECRET_KEY ausente ou fraca no ambiente de produção')
    if JWT_SECRET in weak_values or len(JWT_SECRET) < 32:
        raise RuntimeError('JWT_SECRET ausente ou fraca no ambiente de produção')

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SQLALCHEMY_DATABASE_URI=DATABASE_URL,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    JSON_SORT_KEYS=False,
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)
if DATABASE_URL.startswith('postgresql'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 280}

client_origin = os.getenv('CLIENT_ORIGIN', 'http://localhost:5173')
allowed_origins = [origin.strip().rstrip('/') for origin in client_origin.split(',') if origin.strip()]
if not allowed_origins:
    allowed_origins = ['http://localhost:5173']

CORS(
    app,
    resources={
        r'/api/*': {
            'origins': allowed_origins,
            'methods': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
            'allow_headers': ['Content-Type', 'Authorization', 'X-Request-ID'],
            'max_age': 600,
        }
    },
    supports_credentials=False,
)

socketio = SocketIO(
    app,
    cors_allowed_origins=allowed_origins,
    async_mode='threading',
    ping_interval=25,
    ping_timeout=20,
    max_http_buffer_size=1_000_000,
)
db.init_app(app)

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger('nodo')

TEXT_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
ROOM_DM_RE = re.compile(r'^dm:(\d+):(\d+)$')
ROOM_GROUP_RE = re.compile(r'^group:(\d+)$')
RATE_BUCKET = {}
RATE_LOCK = threading.Lock()
INIT_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Segurança, validação e erros
# ---------------------------------------------------------------------------


def clean_text(value, limit=1000):
    return TEXT_RE.sub('', str(value or '')).strip()[:limit]


def valid_email(value):
    value = clean_text(value, 180).lower()
    return bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value))


def client_ip():
    return request.remote_addr or 'unknown'


def rate_limited(scope, limit=30, window=60, identity=None):
    now = time.monotonic()
    key = f'{scope}:{identity or client_ip()}'
    with RATE_LOCK:
        hits = [stamp for stamp in RATE_BUCKET.get(key, []) if now - stamp < window]
        if len(hits) >= limit:
            RATE_BUCKET[key] = hits
            return True
        hits.append(now)
        RATE_BUCKET[key] = hits
        if len(RATE_BUCKET) > 5000:
            cutoff = now - max(window, 300)
            for old_key in list(RATE_BUCKET)[:1000]:
                kept = [stamp for stamp in RATE_BUCKET[old_key] if stamp >= cutoff]
                if kept:
                    RATE_BUCKET[old_key] = kept
                else:
                    RATE_BUCKET.pop(old_key, None)
    return False


def require_rate(scope, limit=30, window=60, identity=None):
    if rate_limited(scope, limit, window, identity):
        return jsonify({'error': 'Muitas tentativas. Aguarde um pouco.'}), 429
    return None


@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-site'
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, max-age=0'
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


@app.errorhandler(413)
def too_large(_):
    return jsonify({'error': 'Arquivo ou requisição muito grande'}), 413


@app.errorhandler(HTTPException)
def http_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': error.description or 'Requisição inválida'}), error.code
    return error


@app.errorhandler(Exception)
def unexpected_error(error):
    db.session.rollback()
    logger.exception('Erro não tratado em %s', request.path)
    return jsonify({'error': 'Erro interno. Tente novamente.'}), 500


# ---------------------------------------------------------------------------
# Serialização e regras de negócio
# ---------------------------------------------------------------------------


def level_from_xp(xp: int) -> int:
    return max(1, int(xp or 0) // 150 + 1)


def group_level_from_xp(xp: int) -> int:
    return max(1, int(xp or 0) // 250 + 1)


def cosmetic_data(user: User):
    return {
        'frame': user.equipped_frame or '',
        'banner': user.equipped_banner or '',
        'effect': user.equipped_effect or '',
        'badge': user.equipped_badge or '',
        'theme': user.equipped_theme or 'theme-obsidian',
        'nameplate': user.nameplate or '',
    }


def user_public(user: User):
    return {
        'id': user.id,
        'username': user.username,
        'bio': user.bio or '',
        'avatar': user.avatar or '👨‍💻',
        'xp': user.xp or 0,
        'level': user.level or 1,
        'cosmetics': cosmetic_data(user),
        'is_admin': bool(user.is_admin),
    }


def user_private(user: User):
    data = user_public(user)
    data.update(
        {
            'email': user.email,
            'phone': user.phone or '',
            'nodo_coins': user.nodo_coins or 0,
            'streak': user.streak or 0,
            'last_streak_date': user.last_streak_date.isoformat() if user.last_streak_date else None,
            'is_banned': bool(user.is_banned),
        }
    )
    return data


def store_item_payload(item: StoreItem, owned_ids=None):
    owned_ids = owned_ids or set()
    return {
        'id': item.id,
        'name': item.name,
        'description': item.description or '',
        'item_type': item.item_type or 'badge',
        'icon': item.icon or 'badge-founder',
        'rarity': item.rarity or 'comum',
        'price': item.price or 0,
        'owned': item.id in owned_ids,
    }


def post_payload(post: Post, current_user_id=None):
    comments = (
        PostComment.query.filter_by(post_id=post.id)
        .order_by(PostComment.created_at.asc())
        .limit(12)
        .all()
    )
    return {
        'id': post.id,
        'content': post.content,
        'user': user_public(post.user),
        'created_at': post.created_at.isoformat(),
        'likes_count': PostLike.query.filter_by(post_id=post.id).count(),
        'comments_count': PostComment.query.filter_by(post_id=post.id).count(),
        'liked': bool(
            current_user_id
            and PostLike.query.filter_by(post_id=post.id, user_id=current_user_id).first()
        ),
        'comments': [
            {
                'id': comment.id,
                'content': comment.content,
                'user': user_public(comment.user),
                'created_at': comment.created_at.isoformat(),
            }
            for comment in comments
        ],
    }


def chat_payload(message: ChatMessage):
    user = message.user
    return {
        'id': message.id,
        'room': message.room,
        'content': message.content,
        'username': user.username if user else message.username,
        'user_id': message.user_id,
        'user': user_public(user) if user else None,
        'created_at': message.created_at.isoformat(),
    }


def notification_payload(notification: Notification):
    return {
        'id': notification.id,
        'title': notification.title,
        'body': notification.body or '',
        'kind': notification.kind or 'info',
        'action': notification.action or '',
        'is_read': bool(notification.is_read),
        'created_at': notification.created_at.isoformat(),
    }


def touch_streak(user: User):
    today = date.today()
    if user.last_streak_date == today:
        return False
    user.streak = (user.streak or 0) + 1 if user.last_streak_date == today - timedelta(days=1) else 1
    user.last_streak_date = today
    return True


def admin_email_set():
    raw = os.getenv('ADMIN_EMAILS') or os.getenv('ADMIN_EMAIL') or ''
    return {email.strip().lower() for email in raw.split(',') if email.strip()}


def is_admin_email(email):
    return clean_text(email, 180).lower() in admin_email_set()


def sync_configured_admin(user):
    # Só promove uma conta que já existe no banco. Cadastro com e-mail reservado é bloqueado.
    if user and is_admin_email(user.email) and not user.is_admin:
        user.is_admin = True
        user.token_version = (user.token_version or 0) + 1
        db.session.add(user)
    return user


def require_admin(fn):
    @wraps(fn)
    @require_auth
    def wrapper(*args, **kwargs):
        user = request.current_user
        if not user.is_admin:
            return jsonify({'error': 'Acesso apenas para ADM'}), 403
        return fn(*args, **kwargs)

    return wrapper


def notify(user_id, title, body='', kind='info', action=''):
    if user_id:
        db.session.add(
            Notification(
                user_id=user_id,
                title=clean_text(title, 160),
                body=clean_text(body, 400),
                kind=clean_text(kind, 50),
                action=clean_text(action, 120),
            )
        )


def activity(user_id, activity_text, kind='activity'):
    db.session.add(
        Activity(
            user_id=user_id,
            text=clean_text(activity_text, 260),
            kind=clean_text(kind, 50),
        )
    )


def audit(action, target_type='', target_id=None, details=''):
    db.session.add(
        AdminAudit(
            admin_id=getattr(request, 'user_id', None),
            action=clean_text(action, 100),
            target_type=clean_text(target_type, 50),
            target_id=target_id,
            details=clean_text(details, 500),
        )
    )


def friend_row(user_a, user_b):
    return Friend.query.filter(
        ((Friend.requester_id == user_a) & (Friend.addressee_id == user_b))
        | ((Friend.requester_id == user_b) & (Friend.addressee_id == user_a))
    ).first()


def are_friends(user_a, user_b):
    row = friend_row(user_a, user_b)
    return bool(row and row.status == 'accepted')


def room_access(user: User, room: str):
    room = clean_text(room, 120)
    if room == 'global':
        return True, None

    group_match = ROOM_GROUP_RE.fullmatch(room)
    if group_match:
        group = db.session.get(Group, int(group_match.group(1)))
        if not group:
            return False, 'Nodo não encontrado'
        if user.is_admin or any(member.id == user.id for member in group.members):
            return True, None
        return False, 'Entre no Nodo para acessar o chat'

    dm_match = ROOM_DM_RE.fullmatch(room)
    if dm_match:
        first, second = sorted((int(dm_match.group(1)), int(dm_match.group(2))))
        normalized = f'dm:{first}:{second}'
        if normalized != room or user.id not in {first, second}:
            return False, 'DM inválida'
        other = second if user.id == first else first
        if not db.session.get(User, other) or not are_friends(user.id, other):
            return False, 'A DM está disponível apenas entre amigos'
        return True, None

    return False, 'Sala inválida'


# ---------------------------------------------------------------------------
# Inicialização, migrações leves e conteúdo inicial
# ---------------------------------------------------------------------------


def add_column_if_missing(table_name, column_name, definition):
    inspector = inspect(db.engine)
    try:
        columns = {column['name'] for column in inspector.get_columns(table_name)}
    except Exception:
        return
    if column_name in columns:
        return
    preparer = db.engine.dialect.identifier_preparer
    table_sql = preparer.quote(table_name)
    column_sql = preparer.quote(column_name)
    db.session.execute(text(f'ALTER TABLE {table_sql} ADD COLUMN {column_sql} {definition}'))


def run_light_migrations():
    db.create_all()
    additions = {
        'user': {
            'nodo_coins': 'INTEGER DEFAULT 2',
            'streak': 'INTEGER DEFAULT 0',
            'last_streak_date': 'DATE',
            'is_admin': 'BOOLEAN DEFAULT FALSE',
            'is_banned': 'BOOLEAN DEFAULT FALSE',
            # Valor de esquema SQL; não é credencial.
            'token_version': 'INTEGER DEFAULT 0',  # nosec B105
            'equipped_frame': "VARCHAR(80) DEFAULT ''",
            'equipped_banner': "VARCHAR(80) DEFAULT ''",
            'equipped_effect': "VARCHAR(80) DEFAULT ''",
            'equipped_badge': "VARCHAR(80) DEFAULT ''",
            'equipped_theme': "VARCHAR(80) DEFAULT 'theme-obsidian'",
            'nameplate': "VARCHAR(80) DEFAULT ''",
            'updated_at': 'TIMESTAMP',
        },
        'mission': {
            'difficulty': "VARCHAR(30) DEFAULT 'iniciante'",
            'coin_reward': 'INTEGER DEFAULT 1',
            'created_at': 'TIMESTAMP',
            'updated_at': 'TIMESTAMP',
        },
        'store_item': {'rarity': "VARCHAR(30) DEFAULT 'comum'", 'updated_at': 'TIMESTAMP'},
        'group': {'xp': 'INTEGER DEFAULT 0', 'level': 'INTEGER DEFAULT 1', 'updated_at': 'TIMESTAMP'},
        'notification': {'action': "VARCHAR(120) DEFAULT ''", 'updated_at': 'TIMESTAMP'},
        'report': {'reviewed_by': 'INTEGER', 'reviewed_at': 'TIMESTAMP', 'updated_at': 'TIMESTAMP'},
    }
    for table_name, columns in additions.items():
        for column_name, definition in columns.items():
            add_column_if_missing(table_name, column_name, definition)

    for table_name in [
        'friend', 'post', 'post_like', 'post_comment', 'chat_message', 'completed_mission',
        'course', 'purchase', 'achievement', 'user_achievement', 'activity'
    ]:
        add_column_if_missing(table_name, 'updated_at', 'TIMESTAMP')

    # Remove duplicatas antigas antes de criar índices idempotentes.
    db.session.execute(text(
        'DELETE FROM completed_mission WHERE id NOT IN '
        '(SELECT MIN(id) FROM completed_mission GROUP BY user_id, mission_id)'
    ))
    db.session.execute(text(
        'DELETE FROM purchase WHERE id NOT IN '
        '(SELECT MIN(id) FROM purchase GROUP BY user_id, item_id)'
    ))
    db.session.execute(text(
        'DELETE FROM post_like WHERE id NOT IN '
        '(SELECT MIN(id) FROM post_like GROUP BY post_id, user_id)'
    ))
    db.session.execute(text(
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_completed_mission_user_mission '
        'ON completed_mission (user_id, mission_id)'
    ))
    db.session.execute(text(
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_purchase_user_item ON purchase (user_id, item_id)'
    ))
    db.session.execute(text(
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_post_like_user_post ON post_like (post_id, user_id)'
    ))
    db.session.commit()


def seed_store_items():
    cosmetics = [
        ('Moldura Carbon', 'Borda escura.', 'frame', 'frame-carbon', 'comum', 18),
        ('Moldura Neon', 'Borda neon.', 'frame', 'frame-neon', 'raro', 45),
        ('Moldura Glitch', 'Borda glitch.', 'frame', 'frame-glitch', 'épico', 80),
        ('Moldura Founder', 'Borda de fundador.', 'frame', 'frame-founder', 'lendário', 120),
        ('Banner Obsidian', 'Banner escuro.', 'banner', 'banner-obsidian', 'comum', 20),
        ('Banner Aurora', 'Banner aurora.', 'banner', 'banner-aurora', 'raro', 50),
        ('Banner Cyber', 'Banner cyber.', 'banner', 'banner-cyber', 'épico', 90),
        ('Efeito Glow', 'Brilho suave.', 'effect', 'effect-glow', 'raro', 55),
        ('Efeito Code Rain', 'Código animado.', 'effect', 'effect-code-rain', 'épico', 95),
        ('Selo Python', 'Selo Python.', 'badge', 'badge-python', 'comum', 25),
        ('Selo Web Dev', 'Selo Web.', 'badge', 'badge-web', 'comum', 25),
        ('Selo Beta', 'Selo beta.', 'badge', 'badge-beta', 'raro', 45),
        ('Selo Founder', 'Selo founder.', 'badge', 'badge-founder', 'lendário', 140),
        ('Nome Glow', 'Placa glow.', 'nameplate', 'nameplate-glow', 'raro', 60),
        ('Nome Cyber', 'Placa cyber.', 'nameplate', 'nameplate-cyber', 'épico', 100),
        ('Tema Obsidian', 'Tema padrão.', 'theme', 'theme-obsidian', 'comum', 0),
        ('Tema Midnight', 'Tema escuro.', 'theme', 'theme-midnight', 'raro', 35),
        ('Tema Aurora', 'Tema aurora.', 'theme', 'theme-aurora', 'épico', 85),
    ]
    for name, description, item_type, icon, rarity, price in cosmetics:
        item = StoreItem.query.filter_by(icon=icon).first()
        if not item:
            item = StoreItem(icon=icon)
            db.session.add(item)
        item.name = name
        item.description = description
        item.item_type = item_type
        item.rarity = rarity
        item.price = price


def seed_achievements():
    rows = [
        ('first-login', 'Primeiro acesso', 'Entrou na Nodo pela primeira vez.', 'ach-login', 10, 0),
        ('first-post', 'Primeiro post', 'Publicou na comunidade.', 'ach-post', 20, 1),
        ('first-mission', 'Primeira missão', 'Concluiu uma missão.', 'ach-mission', 25, 1),
        ('first-friend', 'Primeiro amigo', 'Adicionou um amigo.', 'ach-friend', 15, 0),
        ('first-purchase', 'Primeiro item', 'Comprou um cosmético.', 'ach-shop', 20, 0),
        ('streak-7', '7 dias', 'Fez streak de 7 dias.', 'ach-streak', 50, 2),
    ]
    for code, title, description, icon, xp, coin in rows:
        achievement = Achievement.query.filter_by(code=code).first()
        if not achievement:
            db.session.add(
                Achievement(
                    code=code,
                    title=title,
                    description=description,
                    icon=icon,
                    xp_reward=xp,
                    coin_reward=coin,
                )
            )


def award(user, code):
    if not user:
        return False
    achievement = Achievement.query.filter_by(code=code).first()
    if not achievement:
        return False
    if UserAchievement.query.filter_by(user_id=user.id, achievement_id=achievement.id).first():
        return False
    db.session.add(UserAchievement(user_id=user.id, achievement_id=achievement.id))
    user.xp = (user.xp or 0) + (achievement.xp_reward or 0)
    user.nodo_coins = (user.nodo_coins or 0) + (achievement.coin_reward or 0)
    user.level = level_from_xp(user.xp)
    notify(user.id, f'Conquista: {achievement.title}', achievement.description, 'achievement', 'achievements')
    activity(user.id, f'{user.username} desbloqueou {achievement.title}', 'achievement')
    return True


def seed_if_empty():
    if Mission.query.count() == 0:
        db.session.add_all(
            [
                Mission(title='Primeiro script Python', description='Explique como criaria um script Python que imprime uma mensagem no terminal.', category='Python', difficulty='iniciante', xp_reward=30, coin_reward=1),
                Mission(title='Página HTML pessoal', description='Explique quais tags HTML usaria para criar uma página com nome, descrição e links.', category='Web', difficulty='iniciante', xp_reward=35, coin_reward=1),
                Mission(title='GitHub básico', description='Explique o passo a passo para criar um repositório e enviar um projeto usando Git.', category='Dev', difficulty='iniciante', xp_reward=45, coin_reward=1),
                Mission(title='Segurança de conta', description='Explique pelo menos 5 formas de proteger uma conta online.', category='Cyber ético', difficulty='iniciante', xp_reward=50, coin_reward=1),
                Mission(title='XSS na defesa', description='Explique o que é XSS e como prevenir.', category='Cyber ético', difficulty='intermediário', xp_reward=65, coin_reward=2),
            ]
        )
    if Course.query.count() == 0:
        db.session.add_all(
            [
                Course(title='Fundamentos de Programação', description='Lógica, variáveis, funções, listas e pequenos projetos.', category='Programação', level='iniciante'),
                Course(title='Web do Zero', description='HTML, CSS, JavaScript e deploy.', category='Web', level='iniciante'),
                Course(title='Python para Projetos', description='Scripts, APIs e automações.', category='Python', level='intermediário'),
                Course(title='Cyber Ético para Devs', description='Autenticação, headers e APIs.', category='Cyber ético', level='intermediário'),
            ]
        )
    seed_store_items()
    seed_achievements()
    db.session.flush()


def initialize_database():
    with INIT_LOCK:
        if getattr(app, '_nodo_db_ready', False):
            return
        run_light_migrations()
        seed_if_empty()
        for configured_email in admin_email_set():
            existing = User.query.filter_by(email=configured_email).first()
            if existing and not existing.is_admin:
                existing.is_admin = True
                existing.token_version = (existing.token_version or 0) + 1
        db.session.commit()
        app._nodo_db_ready = True


@app.before_request
def ensure_database_ready():
    if not getattr(app, '_nodo_db_ready', False):
        initialize_database()


# ---------------------------------------------------------------------------
# Saúde, autenticação e conta
# ---------------------------------------------------------------------------


@app.get('/')
def root():
    return {'name': 'Nodo API', 'version': '4.0.0'}


@app.get('/api/health')
def health():
    db.session.execute(text('SELECT 1'))
    return {'ok': True, 'version': '4.0.0'}


@app.post('/api/auth/register')
def register():
    limited = require_rate('register', 6, 300)
    if limited:
        return limited
    data = request.get_json(silent=True) or {}
    username = clean_text(data.get('username'), 80)
    email = clean_text(data.get('email'), 180).lower()
    password = str(data.get('password') or '')
    if len(username) < 3:
        return jsonify({'error': 'Nome precisa ter pelo menos 3 caracteres'}), 400
    if not valid_email(email):
        return jsonify({'error': 'Email inválido'}), 400
    if len(password) < 10 or len(password) > 128:
        return jsonify({'error': 'Senha precisa ter entre 10 e 128 caracteres'}), 400
    if email == 'demo@nodo.com':
        return jsonify({'error': 'Conta demo desativada'}), 403
    if is_admin_email(email):
        return jsonify({'error': 'Esse e-mail administrativo precisa ser provisionado pelo sistema'}), 403
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email já cadastrado'}), 409

    user = User(username=username, email=email, password_hash=hash_password(password), nodo_coins=2)
    db.session.add(user)
    db.session.flush()
    award(user, 'first-login')
    db.session.commit()
    return {'token': make_token(user.id, user.token_version), 'user': user_private(user)}, 201


@app.post('/api/auth/login')
def login():
    limited = require_rate('login', 10, 300)
    if limited:
        return limited
    data = request.get_json(silent=True) or {}
    email = clean_text(data.get('email'), 180).lower()
    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(data.get('password') or '', user.password_hash):
        return jsonify({'error': 'Email ou senha inválidos'}), 401
    if user.is_banned:
        return jsonify({'error': 'Conta bloqueada'}), 403
    sync_configured_admin(user)
    award(user, 'first-login')
    db.session.commit()
    return {'token': make_token(user.id, user.token_version), 'user': user_private(user)}


@app.get('/api/me')
@require_auth
def me():
    return {'user': user_private(request.current_user)}


@app.put('/api/me')
@require_auth
def update_me():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    username = clean_text(data.get('username'), 80)
    if username:
        if len(username) < 3:
            return jsonify({'error': 'Nome muito curto'}), 400
        user.username = username
    if 'phone' in data:
        user.phone = clean_text(data.get('phone'), 30)
    if 'bio' in data:
        user.bio = clean_text(data.get('bio'), 500)
    if 'avatar' in data:
        avatar = str(data.get('avatar') or '👨‍💻')
        if len(avatar) > 350_000:
            return jsonify({'error': 'Imagem muito pesada'}), 400
        if avatar.startswith('data:') and not re.match(r'^data:image/(png|jpeg|webp);base64,', avatar, re.I):
            return jsonify({'error': 'Formato de imagem inválido'}), 400
        user.avatar = avatar
    db.session.commit()
    return {'user': user_private(user)}


@app.put('/api/me/email')
@require_auth
def update_email():
    limited = require_rate('email-change', 4, 600, request.user_id)
    if limited:
        return limited
    user = request.current_user
    data = request.get_json(silent=True) or {}
    new_email = clean_text(data.get('email'), 180).lower()
    if user.is_admin:
        return jsonify({'error': 'Para proteger o ADM, altere o e-mail diretamente no banco'}), 403
    if not verify_password(data.get('current_password') or '', user.password_hash):
        return jsonify({'error': 'Senha atual incorreta'}), 400
    if not valid_email(new_email):
        return jsonify({'error': 'Email inválido'}), 400
    if is_admin_email(new_email):
        return jsonify({'error': 'Email reservado'}), 403
    if User.query.filter(User.email == new_email, User.id != user.id).first():
        return jsonify({'error': 'Esse email já está em uso'}), 409
    user.email = new_email
    user.token_version = (user.token_version or 0) + 1
    db.session.commit()
    return {'message': 'Email alterado', 'token': make_token(user.id, user.token_version), 'user': user_private(user)}


@app.put('/api/me/password')
@require_auth
def update_password():
    limited = require_rate('password-change', 5, 600, request.user_id)
    if limited:
        return limited
    user = request.current_user
    data = request.get_json(silent=True) or {}
    new_password = str(data.get('new_password') or '')
    if not verify_password(data.get('current_password') or '', user.password_hash):
        return jsonify({'error': 'Senha atual incorreta'}), 400
    if len(new_password) < 10 or len(new_password) > 128:
        return jsonify({'error': 'Nova senha precisa ter entre 10 e 128 caracteres'}), 400
    user.password_hash = hash_password(new_password)
    user.token_version = (user.token_version or 0) + 1
    db.session.commit()
    return {'message': 'Senha alterada', 'token': make_token(user.id, user.token_version)}


@app.post('/api/me/logout-all')
@require_auth
def logout_all():
    user = request.current_user
    user.token_version = (user.token_version or 0) + 1
    db.session.commit()
    return {'message': 'Todas as sessões foram encerradas'}


@app.post('/api/me/equip')
@require_auth
def equip_cosmetic():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    slot = clean_text(data.get('slot'), 30).lower()
    allowed = {
        'frame': 'equipped_frame',
        'banner': 'equipped_banner',
        'effect': 'equipped_effect',
        'badge': 'equipped_badge',
        'theme': 'equipped_theme',
        'nameplate': 'nameplate',
    }
    if slot not in allowed:
        return jsonify({'error': 'Tipo inválido'}), 400
    if data.get('clear'):
        setattr(user, allowed[slot], 'theme-obsidian' if slot == 'theme' else '')
        db.session.commit()
        return {'message': 'Atualizado', 'user': user_private(user)}
    item = db.session.get(StoreItem, data.get('item_id')) if data.get('item_id') else None
    if not item or item.item_type != slot:
        return jsonify({'error': 'Item inválido'}), 400
    owned = Purchase.query.filter_by(user_id=user.id, item_id=item.id).first()
    if not owned and (item.price or 0) > 0:
        return jsonify({'error': 'Você ainda não comprou esse item'}), 403
    setattr(user, allowed[slot], item.icon)
    db.session.commit()
    return {'message': 'Equipado', 'user': user_private(user)}


# ---------------------------------------------------------------------------
# Dashboard, notificações, ranking e busca
# ---------------------------------------------------------------------------


@app.get('/api/dashboard')
@require_auth
def dashboard():
    user = request.current_user
    completed = CompletedMission.query.filter_by(user_id=user.id).count()
    rank_ids = [row.id for row in User.query.filter_by(is_banned=False).order_by(User.xp.desc()).all()]
    position = rank_ids.index(user.id) + 1 if user.id in rank_ids else None
    return {
        'user': user_private(user),
        'stats': {
            'completed_missions': completed,
            'total_missions': Mission.query.count(),
            'ranking_position': position,
            'posts': Post.query.filter_by(user_id=user.id).count(),
            'groups': len(user.groups),
            'achievements': UserAchievement.query.filter_by(user_id=user.id).count(),
        },
        'next_level_xp': user.level * 150,
    }


@app.post('/api/streak/checkin')
@require_auth
def streak_checkin():
    user = User.query.filter_by(id=request.user_id).with_for_update().first_or_404()
    if not touch_streak(user):
        return {'message': 'Check-in já feito', 'user': user_private(user)}
    user.xp = (user.xp or 0) + 15
    user.nodo_coins = (user.nodo_coins or 0) + 1
    user.level = level_from_xp(user.xp)
    if (user.streak or 0) >= 7:
        award(user, 'streak-7')
    activity(user.id, f'{user.username} fez check-in', 'streak')
    db.session.commit()
    return {'message': '+15 XP e +1 NC', 'user': user_private(user)}


@app.get('/api/ranking')
@require_auth
def ranking():
    users = User.query.filter_by(is_banned=False).order_by(User.xp.desc(), User.nodo_coins.desc()).limit(50).all()
    return {'ranking': [{**user_public(user), 'nodo_coins': user.nodo_coins or 0, 'streak': user.streak or 0} for user in users]}


@app.get('/api/activity')
@require_auth
def activities():
    rows = Activity.query.order_by(Activity.created_at.desc()).limit(40).all()
    return {
        'activity': [
            {
                'id': row.id,
                'text': row.text,
                'kind': row.kind,
                'user': user_public(row.user) if row.user else None,
                'created_at': row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@app.get('/api/notifications')
@require_auth
def notifications():
    rows = Notification.query.filter_by(user_id=request.user_id).order_by(Notification.created_at.desc()).limit(80).all()
    return {
        'notifications': [notification_payload(row) for row in rows],
        'unread': Notification.query.filter_by(user_id=request.user_id, is_read=False).count(),
    }


@app.post('/api/notifications/read')
@require_auth
def notifications_read():
    Notification.query.filter_by(user_id=request.user_id, is_read=False).update({'is_read': True})
    db.session.commit()
    return {'message': 'ok'}


@app.get('/api/achievements')
@require_auth
def achievements():
    owned = {row.achievement_id for row in UserAchievement.query.filter_by(user_id=request.user_id).all()}
    rows = Achievement.query.order_by(Achievement.id.asc()).all()
    return {
        'achievements': [
            {
                'id': row.id,
                'code': row.code,
                'title': row.title,
                'description': row.description,
                'icon': row.icon,
                'xp_reward': row.xp_reward,
                'coin_reward': row.coin_reward,
                'unlocked': row.id in owned,
            }
            for row in rows
        ]
    }


@app.get('/api/search')
@require_auth
def global_search():
    query = clean_text(request.args.get('q'), 80)
    if len(query) < 2:
        return {'users': [], 'groups': [], 'posts': []}
    users = User.query.filter(User.is_banned.is_(False), User.username.ilike(f'%{query}%')).limit(10).all()
    groups = Group.query.filter(Group.name.ilike(f'%{query}%')).limit(10).all()
    posts = Post.query.filter(Post.content.ilike(f'%{query}%')).order_by(Post.created_at.desc()).limit(10).all()
    return {
        'users': [user_public(user) for user in users if user.id != request.user_id],
        'groups': [{'id': group.id, 'name': group.name, 'topic': group.topic, 'members_count': len(group.members)} for group in groups],
        'posts': [post_payload(post, request.user_id) for post in posts],
    }


# ---------------------------------------------------------------------------
# Amigos, Nodos e comunidade
# ---------------------------------------------------------------------------


@app.get('/api/users')
@require_auth
def search_users():
    query_text = clean_text(request.args.get('q'), 80)
    query = User.query.filter_by(is_banned=False)
    if query_text:
        query = query.filter(User.username.ilike(f'%{query_text}%'))
    return {'users': [user_public(user) for user in query.limit(30).all() if user.id != request.user_id]}


@app.post('/api/friends/<int:user_id>')
@require_auth
def add_friend(user_id):
    if user_id == request.user_id:
        return jsonify({'error': 'Você não pode adicionar você mesmo'}), 400
    target = User.query.filter_by(id=user_id, is_banned=False).first()
    if not target:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    existing = friend_row(request.user_id, user_id)
    if existing:
        return {'message': 'Pedido já existe'}
    me_user = request.current_user
    db.session.add(Friend(requester_id=request.user_id, addressee_id=user_id, status='pending'))
    notify(user_id, 'Pedido de amizade', f'{me_user.username} quer te adicionar', 'friend', 'friends')
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {'message': 'Pedido já existe'}
    return {'message': 'Pedido enviado'}


@app.post('/api/friends/<int:friend_id>/accept')
@require_auth
def accept_friend(friend_id):
    row = Friend.query.get_or_404(friend_id)
    if row.addressee_id != request.user_id or row.status != 'pending':
        return jsonify({'error': 'Sem permissão'}), 403
    row.status = 'accepted'
    user = request.current_user
    other = db.session.get(User, row.requester_id)
    award(user, 'first-friend')
    award(other, 'first-friend')
    notify(row.requester_id, 'Pedido aceito', f'{user.username} aceitou seu pedido', 'friend', 'friends')
    db.session.commit()
    return {'message': 'Amigo adicionado'}


@app.post('/api/friends/<int:friend_id>/reject')
@require_auth
def reject_friend(friend_id):
    row = Friend.query.get_or_404(friend_id)
    if row.addressee_id != request.user_id or row.status != 'pending':
        return jsonify({'error': 'Sem permissão'}), 403
    db.session.delete(row)
    db.session.commit()
    return {'message': 'Pedido recusado'}


@app.delete('/api/friends/user/<int:user_id>')
@require_auth
def remove_friend(user_id):
    row = friend_row(request.user_id, user_id)
    if not row or row.status != 'accepted':
        return jsonify({'error': 'Amizade não encontrada'}), 404
    db.session.delete(row)
    db.session.commit()
    return {'message': 'Amizade removida'}


@app.get('/api/friends')
@require_auth
def friends():
    rows = Friend.query.filter(
        (Friend.requester_id == request.user_id) | (Friend.addressee_id == request.user_id)
    ).all()
    accepted_ids = [
        row.addressee_id if row.requester_id == request.user_id else row.requester_id
        for row in rows
        if row.status == 'accepted'
    ]
    pending_in = [row for row in rows if row.status == 'pending' and row.addressee_id == request.user_id]
    users = User.query.filter(User.id.in_(accepted_ids), User.is_banned.is_(False)).all() if accepted_ids else []
    return {
        'friends': [user_public(user) for user in users],
        'pending': [
            {
                'id': row.id,
                'user': user_public(db.session.get(User, row.requester_id)),
                'created_at': row.created_at.isoformat(),
            }
            for row in pending_in
        ],
    }


@app.get('/api/groups')
@require_auth
def list_groups():
    groups = Group.query.order_by(Group.created_at.desc()).limit(100).all()
    return {
        'groups': [
            {
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'topic': group.topic,
                'owner_id': group.owner_id,
                'members_count': len(group.members),
                'xp': group.xp or 0,
                'level': group.level or 1,
                'is_member': any(member.id == request.user_id for member in group.members),
            }
            for group in groups
        ]
    }


@app.get('/api/my-groups')
@require_auth
def my_groups():
    user = request.current_user
    return {
        'groups': [
            {
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'topic': group.topic,
                'members_count': len(group.members),
                'level': group.level or 1,
            }
            for group in user.groups
        ]
    }


@app.post('/api/groups')
@require_auth
def create_group():
    limited = require_rate('group-create', 4, 3600, request.user_id)
    if limited:
        return limited
    data = request.get_json(silent=True) or {}
    name = clean_text(data.get('name'), 120)
    if len(name) < 3:
        return jsonify({'error': 'Nome do Nodo muito curto'}), 400
    user = request.current_user
    group = Group(
        name=name,
        description=clean_text(data.get('description'), 400),
        topic=clean_text(data.get('topic') or 'Programação', 80),
        owner_id=user.id,
        members=[user],
    )
    db.session.add(group)
    activity(user.id, f'{user.username} criou o Nodo {name}', 'group')
    db.session.commit()
    return {'message': 'Nodo criado', 'group_id': group.id}, 201


@app.post('/api/groups/<int:group_id>/join')
@require_auth
def join_group(group_id):
    group = Group.query.get_or_404(group_id)
    user = request.current_user
    if user not in group.members:
        group.members.append(user)
        group.xp = (group.xp or 0) + 10
        group.level = group_level_from_xp(group.xp)
        activity(user.id, f'{user.username} entrou em {group.name}', 'group')
        db.session.commit()
    return {'message': 'Você entrou no Nodo'}


@app.post('/api/groups/<int:group_id>/leave')
@require_auth
def leave_group_api(group_id):
    group = Group.query.get_or_404(group_id)
    user = request.current_user
    if group.owner_id == user.id:
        return jsonify({'error': 'O dono não pode sair sem apagar ou transferir o Nodo'}), 400
    if user in group.members:
        group.members.remove(user)
        db.session.commit()
    return {'message': 'Você saiu do Nodo'}


@app.get('/api/posts')
@require_auth
def list_posts():
    limit = max(1, min(int(request.args.get('limit', 30)), 50))
    posts = Post.query.order_by(Post.created_at.desc()).limit(limit).all()
    return {'posts': [post_payload(post, request.user_id) for post in posts]}


@app.post('/api/posts')
@require_auth
def create_post():
    limited = require_rate('post', 12, 60, request.user_id)
    if limited:
        return limited
    content = clean_text((request.get_json(silent=True) or {}).get('content'), 1000)
    if len(content) < 2:
        return jsonify({'error': 'Digite algo'}), 400
    user = request.current_user
    post = Post(content=content, user_id=user.id)
    db.session.add(post)
    activity(user.id, f'{user.username} publicou na comunidade', 'post')
    db.session.flush()
    award(user, 'first-post')
    db.session.commit()
    return {'message': 'Publicado', 'post': post_payload(post, request.user_id)}, 201


@app.post('/api/posts/<int:post_id>/like')
@require_auth
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    existing = PostLike.query.filter_by(post_id=post.id, user_id=request.user_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return {'liked': False, 'post': post_payload(post, request.user_id)}
    db.session.add(PostLike(post_id=post.id, user_id=request.user_id))
    if post.user_id != request.user_id:
        notify(post.user_id, 'Curtida', f'{request.current_user.username} curtiu seu post', 'like', 'community')
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    return {'liked': True, 'post': post_payload(post, request.user_id)}


@app.post('/api/posts/<int:post_id>/comments')
@require_auth
def comment_post(post_id):
    limited = require_rate('comment', 20, 60, request.user_id)
    if limited:
        return limited
    post = Post.query.get_or_404(post_id)
    content = clean_text((request.get_json(silent=True) or {}).get('content'), 700)
    if not content:
        return jsonify({'error': 'Comentário vazio'}), 400
    user = request.current_user
    db.session.add(PostComment(post_id=post.id, user_id=user.id, content=content))
    if post.user_id != user.id:
        notify(post.user_id, 'Comentário', f'{user.username} comentou seu post', 'comment', 'community')
    db.session.commit()
    return {'message': 'Comentado', 'post': post_payload(post, request.user_id)}


@app.post('/api/reports')
@require_auth
def create_report():
    limited = require_rate('report', 8, 600, request.user_id)
    if limited:
        return limited
    data = request.get_json(silent=True) or {}
    target_type = clean_text(data.get('target_type'), 40)
    try:
        target_id = int(data.get('target_id') or 0)
    except (TypeError, ValueError):
        target_id = 0
    reason = clean_text(data.get('reason'), 400)
    if target_type not in {'post', 'user', 'group'} or target_id <= 0:
        return jsonify({'error': 'Denúncia inválida'}), 400
    duplicate = Report.query.filter_by(
        reporter_id=request.user_id,
        target_type=target_type,
        target_id=target_id,
        status='open',
    ).first()
    if duplicate:
        return {'message': 'Denúncia já enviada'}
    db.session.add(Report(reporter_id=request.user_id, target_type=target_type, target_id=target_id, reason=reason))
    db.session.commit()
    return {'message': 'Denúncia enviada'}, 201


# ---------------------------------------------------------------------------
# Missões, cursos, loja e personalização
# ---------------------------------------------------------------------------


@app.get('/api/missions')
@require_auth
def missions():
    done = {row.mission_id for row in CompletedMission.query.filter_by(user_id=request.user_id).all()}
    rows = Mission.query.order_by(Mission.id.asc()).all()
    return {
        'missions': [
            {
                'id': mission.id,
                'title': mission.title,
                'description': mission.description,
                'category': mission.category,
                'difficulty': mission.difficulty or 'iniciante',
                'xp_reward': mission.xp_reward or 0,
                'coin_reward': mission.coin_reward or 0,
                'completed': mission.id in done,
            }
            for mission in rows
        ]
    }


@app.post('/api/missions/<int:mission_id>/submit')
@require_auth
def submit_mission(mission_id):
    limited = require_rate('mission-submit', 12, 300, request.user_id)
    if limited:
        return limited
    mission = Mission.query.get_or_404(mission_id)
    answer = clean_text((request.get_json(silent=True) or {}).get('answer'), 1200)
    if len(answer) < 20:
        return jsonify({'error': 'Resposta muito curta'}), 400
    user = User.query.filter_by(id=request.user_id).with_for_update().first_or_404()
    if CompletedMission.query.filter_by(user_id=user.id, mission_id=mission.id).first():
        return jsonify({'error': 'Missão já concluída'}), 409
    user.xp = (user.xp or 0) + (mission.xp_reward or 0)
    user.nodo_coins = (user.nodo_coins or 0) + (mission.coin_reward or 0)
    user.level = level_from_xp(user.xp)
    touch_streak(user)
    db.session.add(CompletedMission(user_id=user.id, mission_id=mission.id, answer=answer))
    activity(user.id, f'{user.username} completou uma missão', 'mission')
    award(user, 'first-mission')
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Missão já concluída'}), 409
    return {'message': f'+{mission.xp_reward} XP e +{mission.coin_reward} NC', 'user': user_private(user)}


@app.get('/api/courses')
@require_auth
def courses():
    rows = Course.query.order_by(Course.id.asc()).all()
    return {'courses': [{'id': row.id, 'title': row.title, 'description': row.description, 'category': row.category, 'level': row.level} for row in rows]}


@app.get('/api/store')
@require_auth
def store():
    owned = {row.item_id for row in Purchase.query.filter_by(user_id=request.user_id).all()}
    items = StoreItem.query.order_by(StoreItem.price.asc(), StoreItem.id.asc()).all()
    return {'items': [store_item_payload(item, owned) for item in items]}


@app.post('/api/store/<int:item_id>/purchase')
@require_auth
def purchase(item_id):
    limited = require_rate('purchase', 10, 60, request.user_id)
    if limited:
        return limited
    item = StoreItem.query.get_or_404(item_id)
    user = User.query.filter_by(id=request.user_id).with_for_update().first_or_404()
    if Purchase.query.filter_by(user_id=user.id, item_id=item.id).first():
        return jsonify({'error': 'Você já tem esse item'}), 409
    if (user.nodo_coins or 0) < (item.price or 0):
        return jsonify({'error': 'NC insuficiente'}), 400
    user.nodo_coins -= item.price or 0
    db.session.add(Purchase(user_id=user.id, item_id=item.id))
    activity(user.id, f'{user.username} comprou {item.name}', 'store')
    award(user, 'first-purchase')
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Você já tem esse item'}), 409
    return {'message': 'Comprado', 'user': user_private(user)}


# ---------------------------------------------------------------------------
# Administração
# ---------------------------------------------------------------------------


@app.get('/api/admin/overview')
@require_admin
def admin_overview():
    users = User.query.order_by(User.created_at.desc()).limit(150).all()
    posts = Post.query.order_by(Post.created_at.desc()).limit(100).all()
    groups = Group.query.order_by(Group.created_at.desc()).limit(100).all()
    items = StoreItem.query.order_by(StoreItem.id.desc()).limit(150).all()
    mission_rows = Mission.query.order_by(Mission.id.desc()).limit(150).all()
    reports = Report.query.order_by(Report.created_at.desc()).limit(100).all()
    audits = AdminAudit.query.order_by(AdminAudit.created_at.desc()).limit(80).all()
    return {
        'summary': {
            'users': User.query.count(),
            'missions': Mission.query.count(),
            'posts': Post.query.count(),
            'groups': Group.query.count(),
            'courses': Course.query.count(),
            'store_items': StoreItem.query.count(),
            'reports': Report.query.filter_by(status='open').count(),
        },
        'users': [user_private(user) for user in users],
        'posts': [post_payload(post, request.user_id) for post in posts],
        'groups': [{'id': group.id, 'name': group.name, 'topic': group.topic, 'description': group.description, 'members_count': len(group.members), 'level': group.level or 1} for group in groups],
        'store_items': [store_item_payload(item) for item in items],
        'missions': [{'id': mission.id, 'title': mission.title, 'description': mission.description, 'category': mission.category, 'difficulty': mission.difficulty, 'xp_reward': mission.xp_reward, 'coin_reward': mission.coin_reward} for mission in mission_rows],
        'reports': [{'id': report.id, 'target_type': report.target_type, 'target_id': report.target_id, 'reason': report.reason, 'status': report.status, 'created_at': report.created_at.isoformat()} for report in reports],
        'audit': [{'id': row.id, 'admin': row.admin.username if row.admin else 'Sistema', 'action': row.action, 'target_type': row.target_type, 'target_id': row.target_id, 'details': row.details, 'created_at': row.created_at.isoformat()} for row in audits],
    }


@app.patch('/api/admin/users/<int:user_id>')
@require_admin
def admin_update_user(user_id):
    target = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    configured = is_admin_email(target.email)
    changed = []

    if 'is_admin' in data:
        desired = bool(data['is_admin'])
        if configured and not desired:
            return jsonify({'error': 'ADM configurado no Render não pode ser removido aqui'}), 400
        if target.id == request.user_id and not desired:
            return jsonify({'error': 'Você não pode remover seu próprio ADM'}), 400
        if target.is_admin != desired:
            target.is_admin = desired
            target.token_version = (target.token_version or 0) + 1
            changed.append('admin')

    if 'is_banned' in data:
        desired = bool(data['is_banned'])
        if target.id == request.user_id or configured:
            return jsonify({'error': 'Essa conta não pode ser banida'}), 400
        if target.is_banned != desired:
            target.is_banned = desired
            target.token_version = (target.token_version or 0) + 1
            changed.append('ban')

    if 'nodo_coins' in data:
        target.nodo_coins = max(0, min(int(data.get('nodo_coins') or 0), 1_000_000))
        changed.append('coins')
    if 'xp' in data:
        target.xp = max(0, min(int(data.get('xp') or 0), 10_000_000))
        target.level = level_from_xp(target.xp)
        changed.append('xp')
    if 'username' in data:
        username = clean_text(data.get('username'), 80)
        if len(username) < 3:
            return jsonify({'error': 'Nome muito curto'}), 400
        target.username = username
        changed.append('username')

    audit('update-user', 'user', target.id, ', '.join(changed) or 'sem mudanças')
    db.session.commit()
    return {'message': 'Usuário atualizado', 'user': user_private(target)}


@app.post('/api/admin/missions')
@require_admin
def admin_create_mission():
    data = request.get_json(silent=True) or {}
    title = clean_text(data.get('title'), 160)
    description = clean_text(data.get('description'), 600)
    if len(title) < 3 or len(description) < 10:
        return jsonify({'error': 'Título ou descrição muito curtos'}), 400
    mission = Mission(
        title=title,
        description=description,
        category=clean_text(data.get('category') or 'Programação', 80),
        difficulty=clean_text(data.get('difficulty') or 'iniciante', 30),
        xp_reward=max(0, min(int(data.get('xp_reward') or 30), 300)),
        coin_reward=max(0, min(int(data.get('coin_reward') or 1), 3)),
    )
    db.session.add(mission)
    db.session.flush()
    audit('create-mission', 'mission', mission.id, mission.title)
    db.session.commit()
    return {'message': 'Missão criada', 'mission_id': mission.id}, 201


@app.delete('/api/admin/missions/<int:mission_id>')
@require_admin
def admin_delete_mission(mission_id):
    mission = Mission.query.get_or_404(mission_id)
    CompletedMission.query.filter_by(mission_id=mission.id).delete()
    audit('delete-mission', 'mission', mission.id, mission.title)
    db.session.delete(mission)
    db.session.commit()
    return {'message': 'Missão apagada'}


@app.post('/api/admin/store')
@require_admin
def admin_create_store_item():
    data = request.get_json(silent=True) or {}
    name = clean_text(data.get('name'), 120)
    icon = clean_text(data.get('icon'), 80)
    if len(name) < 2 or len(icon) < 2:
        return jsonify({'error': 'Nome e identificador são obrigatórios'}), 400
    if StoreItem.query.filter_by(icon=icon).first():
        return jsonify({'error': 'Esse identificador já existe'}), 409
    item_type = clean_text(data.get('item_type') or 'badge', 50)
    if item_type not in {'frame', 'banner', 'effect', 'badge', 'nameplate', 'theme'}:
        return jsonify({'error': 'Tipo inválido'}), 400
    item = StoreItem(
        name=name,
        description=clean_text(data.get('description'), 400),
        item_type=item_type,
        icon=icon,
        rarity=clean_text(data.get('rarity') or 'comum', 30),
        price=max(0, min(int(data.get('price') or 25), 100_000)),
    )
    db.session.add(item)
    db.session.flush()
    audit('create-store-item', 'store_item', item.id, item.name)
    db.session.commit()
    return {'message': 'Item criado', 'item_id': item.id}, 201


@app.delete('/api/admin/store/<int:item_id>')
@require_admin
def admin_delete_store_item(item_id):
    item = StoreItem.query.get_or_404(item_id)
    Purchase.query.filter_by(item_id=item.id).delete()
    audit('delete-store-item', 'store_item', item.id, item.name)
    db.session.delete(item)
    db.session.commit()
    return {'message': 'Item apagado'}


@app.delete('/api/admin/posts/<int:post_id>')
@require_admin
def admin_delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    PostLike.query.filter_by(post_id=post.id).delete()
    PostComment.query.filter_by(post_id=post.id).delete()
    audit('delete-post', 'post', post.id, post.content[:120])
    db.session.delete(post)
    db.session.commit()
    return {'message': 'Post apagado'}


@app.delete('/api/admin/groups/<int:group_id>')
@require_admin
def admin_delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    ChatMessage.query.filter_by(room=f'group:{group.id}').delete()
    audit('delete-group', 'group', group.id, group.name)
    db.session.delete(group)
    db.session.commit()
    return {'message': 'Nodo apagado'}


@app.patch('/api/admin/reports/<int:report_id>')
@require_admin
def admin_update_report(report_id):
    report = Report.query.get_or_404(report_id)
    status = clean_text((request.get_json(silent=True) or {}).get('status') or 'closed', 30)
    if status not in {'open', 'reviewing', 'closed', 'dismissed'}:
        return jsonify({'error': 'Status inválido'}), 400
    report.status = status
    report.reviewed_by = request.user_id
    report.reviewed_at = datetime.utcnow()
    audit('update-report', 'report', report.id, status)
    db.session.commit()
    return {'message': 'Denúncia atualizada'}


# ---------------------------------------------------------------------------
# Chat e Nodo AI
# ---------------------------------------------------------------------------


@app.get('/api/chat/history')
@require_auth
def chat_history():
    room = clean_text(request.args.get('room') or 'global', 120)
    allowed, reason = room_access(request.current_user, room)
    if not allowed:
        return jsonify({'error': reason}), 403
    limit = max(1, min(int(request.args.get('limit', 80)), 100))
    query = ChatMessage.query.filter_by(room=room)
    before = request.args.get('before')
    if before and str(before).isdigit():
        query = query.filter(ChatMessage.id < int(before))
    messages = query.order_by(ChatMessage.id.desc()).limit(limit).all()
    messages.reverse()
    return {'messages': [chat_payload(message) for message in messages]}


@app.post('/api/chat/message')
@require_auth
def chat_send_message():
    limited = require_rate('chat', 35, 60, request.user_id)
    if limited:
        return limited
    data = request.get_json(silent=True) or {}
    room = clean_text(data.get('room') or 'global', 120)
    content = clean_text(data.get('content'), 1000)
    allowed, reason = room_access(request.current_user, room)
    if not allowed:
        return jsonify({'error': reason}), 403
    if not content:
        return jsonify({'error': 'Mensagem vazia'}), 400
    message = ChatMessage(room=room, content=content, username=request.current_user.username, user_id=request.user_id)
    db.session.add(message)
    db.session.commit()
    payload = chat_payload(message)
    socketio.emit('message', payload, to=room)
    return {'message': payload}, 201


@app.post('/api/ai')
@require_auth
def ai_chat():
    limited = require_rate('ai', 15, 300, request.user_id)
    if limited:
        return limited
    prompt = clean_text((request.get_json(silent=True) or {}).get('message'), 2500)
    api_key = os.getenv('OPENAI_API_KEY')
    if not prompt:
        return jsonify({'error': 'Mensagem vazia'}), 400
    if not api_key:
        return {'reply': 'Nodo AI ainda não está configurada.'}
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
            messages=[
                {
                    'role': 'system',
                    'content': 'Você é a Nodo AI. Ajude com programação, projetos, estudo e segurança ética. Recuse invasão, golpes, malware e crime.',
                },
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.4,
        )
        return {'reply': response.choices[0].message.content}
    except Exception:
        logger.exception('Falha na Nodo AI')
        return jsonify({'error': 'A Nodo AI está indisponível agora'}), 503


def socket_user_from_data(data):
    token = (data or {}).get('token') or ''
    try:
        payload = decode_token(token)
        user = db.session.get(User, int(payload['sub']))
        if not user or user.is_banned or int(payload.get('ver', -1)) != int(user.token_version or 0):
            return None
        return user
    except Exception:
        return None


@socketio.on('join')
def on_join(data):
    user = socket_user_from_data(data)
    if not user:
        emit('system', {'error': 'Sessão inválida'}, to=request.sid)
        return
    room = clean_text((data or {}).get('room') or 'global', 120)
    allowed, reason = room_access(user, room)
    if not allowed:
        emit('system', {'error': reason}, to=request.sid)
        return
    join_room(room)
    emit('system', {'message': 'Conectado', 'room': room}, to=request.sid)


@socketio.on('leave')
def on_leave(data):
    user = socket_user_from_data(data)
    if not user:
        return
    room = clean_text((data or {}).get('room') or 'global', 120)
    leave_room(room)


@socketio.on('message')
def on_message(data):
    user = socket_user_from_data(data)
    if not user:
        emit('system', {'error': 'Sessão inválida'}, to=request.sid)
        return
    room = clean_text((data or {}).get('room') or 'global', 120)
    content = clean_text((data or {}).get('content'), 1000)
    allowed, reason = room_access(user, room)
    if not allowed:
        emit('system', {'error': reason}, to=request.sid)
        return
    if not content or rate_limited('socket-chat', 35, 60, user.id):
        return
    message = ChatMessage(room=room, content=content, username=user.username, user_id=user.id)
    db.session.add(message)
    db.session.commit()
    emit('message', chat_payload(message), to=room)


if __name__ == '__main__':
    with app.app_context():
        initialize_database()
    socketio.run(
        app,
        # O Render exige bind em todas as interfaces do contêiner.
        host='0.0.0.0',  # nosec B104
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG') == '1',
        allow_unsafe_werkzeug=not IS_PRODUCTION,
    )
