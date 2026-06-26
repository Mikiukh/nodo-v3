import os
import re
import time
from datetime import date, timedelta
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from openai import OpenAI
from sqlalchemy import inspect, text

from models import (
    db, User, Friend, Group, Post, PostLike, PostComment, ChatMessage, Mission,
    CompletedMission, Course, StoreItem, Purchase, Achievement, UserAchievement,
    Notification, Activity, Report
)
from security import hash_password, verify_password, make_token, decode_token, require_auth

# ---------- config ----------

def normalize_database_url(url: str) -> str:
    if url and url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    return url

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-local-only')
app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_url(os.getenv('DATABASE_URL', 'sqlite:///nodo.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

client_origin = os.getenv('CLIENT_ORIGIN', 'http://localhost:5173')
allowed_origins = [o.strip().rstrip('/') for o in client_origin.split(',') if o.strip()]
CORS(
    app,
    resources={r'/api/*': {'origins': allowed_origins or ['http://localhost:5173'], 'methods': ['GET','POST','PUT','PATCH','DELETE','OPTIONS'], 'allow_headers': ['Content-Type','Authorization']}},
    supports_credentials=True,
)
socketio = SocketIO(app, cors_allowed_origins=allowed_origins or ['http://localhost:5173'], async_mode='threading')
db.init_app(app)

RATE_BUCKET = {}
TEXT_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')

# ---------- security helpers ----------

def clean_text(value, limit=1000):
    value = TEXT_RE.sub('', str(value or '')).strip()
    return value[:limit]


def client_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    return (forwarded.split(',')[0].strip() if forwarded else request.remote_addr) or 'unknown'


def rate_limited(scope, limit=30, window=60):
    now = time.time()
    key = f'{scope}:{client_ip()}'
    hits = [t for t in RATE_BUCKET.get(key, []) if now - t < window]
    if len(hits) >= limit:
        return True
    hits.append(now)
    RATE_BUCKET[key] = hits
    return False


def require_rate(scope, limit=30, window=60):
    if rate_limited(scope, limit, window):
        return jsonify({'error': 'Muitas tentativas. Espere um pouco.'}), 429
    return None


@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Cache-Control'] = 'no-store' if request.path.startswith('/api/') else response.headers.get('Cache-Control', '')
    return response

# ---------- serializers ----------

def level_from_xp(xp: int) -> int:
    return max(1, int(xp or 0) // 150 + 1)


def group_level_from_xp(xp: int) -> int:
    return max(1, int(xp or 0) // 250 + 1)


def cosmetic_data(u: User):
    return {
        'frame': getattr(u, 'equipped_frame', '') or '',
        'banner': getattr(u, 'equipped_banner', '') or '',
        'effect': getattr(u, 'equipped_effect', '') or '',
        'badge': getattr(u, 'equipped_badge', '') or '',
        'theme': getattr(u, 'equipped_theme', '') or 'theme-obsidian',
        'nameplate': getattr(u, 'nameplate', '') or '',
    }


def user_public(u: User):
    return {
        'id': u.id,
        'username': u.username,
        'bio': u.bio or '',
        'avatar': u.avatar or '👨‍💻',
        'xp': u.xp or 0,
        'level': u.level or 1,
        'cosmetics': cosmetic_data(u),
        'is_admin': bool(getattr(u, 'is_admin', False)),
        'is_banned': bool(getattr(u, 'is_banned', False)),
    }


def user_private(u: User):
    data = user_public(u)
    data.update({
        'email': u.email,
        'phone': u.phone or '',
        'nodo_coins': u.nodo_coins or 0,
        'streak': u.streak or 0,
        'last_streak_date': u.last_streak_date.isoformat() if u.last_streak_date else None,
    })
    return data


def store_item_payload(i: StoreItem, owned_ids=None):
    owned_ids = owned_ids or set()
    return {'id': i.id, 'name': i.name, 'description': i.description or '', 'item_type': i.item_type or 'badge', 'icon': i.icon or 'badge-founder', 'rarity': i.rarity or 'comum', 'price': i.price or 0, 'owned': i.id in owned_ids}


def post_payload(p: Post, current_user_id=None):
    likes = PostLike.query.filter_by(post_id=p.id).count()
    comments = PostComment.query.filter_by(post_id=p.id).order_by(PostComment.created_at.asc()).limit(8).all()
    liked = bool(current_user_id and PostLike.query.filter_by(post_id=p.id, user_id=current_user_id).first())
    return {
        'id': p.id,
        'content': p.content,
        'user': user_public(p.user),
        'created_at': p.created_at.isoformat(),
        'likes_count': likes,
        'comments_count': PostComment.query.filter_by(post_id=p.id).count(),
        'liked': liked,
        'comments': [{'id': c.id, 'content': c.content, 'user': user_public(c.user), 'created_at': c.created_at.isoformat()} for c in comments],
    }


def notification_payload(n: Notification):
    return {'id': n.id, 'title': n.title, 'body': n.body or '', 'kind': n.kind or 'info', 'is_read': bool(n.is_read), 'created_at': n.created_at.isoformat()}


def touch_streak(u: User):
    today = date.today()
    if u.last_streak_date == today:
        return False
    if u.last_streak_date == today - timedelta(days=1):
        u.streak = (u.streak or 0) + 1
    else:
        u.streak = 1
    u.last_streak_date = today
    return True


def admin_email_set():
    raw = os.getenv('ADMIN_EMAILS') or os.getenv('ADMIN_EMAIL') or ''
    return {email.strip().lower() for email in raw.split(',') if email.strip()}


def is_admin_email(email: str) -> bool:
    return (email or '').strip().lower() in admin_email_set()


def sync_admin_flag(u: User):
    if u and is_admin_email(u.email) and not u.is_admin:
        u.is_admin = True
        db.session.add(u)
        db.session.commit()
    return u


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        u = User.query.get_or_404(request.user_id)
        sync_admin_flag(u)
        if not u.is_admin:
            return jsonify({'error': 'Acesso apenas para admin'}), 403
        return fn(*args, **kwargs)
    return require_auth(wrapper)


def notify(user_id, title, body='', kind='info'):
    if not user_id:
        return
    db.session.add(Notification(user_id=user_id, title=clean_text(title, 160), body=clean_text(body, 400), kind=clean_text(kind, 50)))


def activity(user_id, text, kind='activity'):
    db.session.add(Activity(user_id=user_id, text=clean_text(text, 260), kind=clean_text(kind, 50)))

# ---------- migrations/seed ----------

def add_column_if_missing(table_name, column_name, definition):
    inspector = inspect(db.engine)
    try:
        cols = {c['name'] for c in inspector.get_columns(table_name)}
    except Exception:
        return
    if column_name in cols:
        return
    table_sql = '"user"' if table_name == 'user' else table_name
    db.session.execute(text(f'ALTER TABLE {table_sql} ADD COLUMN {column_name} {definition}'))


def run_light_migrations():
    db.create_all()
    user_additions = {
        'nodo_coins': 'INTEGER DEFAULT 2', 'streak': 'INTEGER DEFAULT 0', 'last_streak_date': 'DATE',
        'is_admin': 'BOOLEAN DEFAULT FALSE', 'is_banned': 'BOOLEAN DEFAULT FALSE',
        'equipped_frame': "VARCHAR(80) DEFAULT ''", 'equipped_banner': "VARCHAR(80) DEFAULT ''",
        'equipped_effect': "VARCHAR(80) DEFAULT ''", 'equipped_badge': "VARCHAR(80) DEFAULT ''",
        'equipped_theme': "VARCHAR(80) DEFAULT 'theme-obsidian'", 'nameplate': "VARCHAR(80) DEFAULT ''",
    }
    for col, definition in user_additions.items(): add_column_if_missing('user', col, definition)
    for col, definition in {'difficulty': "VARCHAR(30) DEFAULT 'iniciante'", 'coin_reward': 'INTEGER DEFAULT 1', 'created_at': 'TIMESTAMP'}.items(): add_column_if_missing('mission', col, definition)
    for col, definition in {'rarity': "VARCHAR(30) DEFAULT 'comum'"}.items(): add_column_if_missing('store_item', col, definition)
    for col, definition in {'xp': 'INTEGER DEFAULT 0', 'level': 'INTEGER DEFAULT 1'}.items(): add_column_if_missing('group', col, definition)
    db.session.commit()


def seed_store_items():
    cosmetics = [
        {'name':'Moldura Carbon','description':'Borda escura para avatar.','item_type':'frame','icon':'frame-carbon','rarity':'comum','price':18},
        {'name':'Moldura Neon','description':'Borda neon para avatar.','item_type':'frame','icon':'frame-neon','rarity':'raro','price':45},
        {'name':'Moldura Glitch','description':'Borda glitch.','item_type':'frame','icon':'frame-glitch','rarity':'épico','price':80},
        {'name':'Moldura Founder','description':'Borda de fundador.','item_type':'frame','icon':'frame-founder','rarity':'lendário','price':120},
        {'name':'Banner Obsidian','description':'Banner escuro.','item_type':'banner','icon':'banner-obsidian','rarity':'comum','price':20},
        {'name':'Banner Aurora','description':'Banner suave.','item_type':'banner','icon':'banner-aurora','rarity':'raro','price':50},
        {'name':'Banner Cyber','description':'Banner cyber.','item_type':'banner','icon':'banner-cyber','rarity':'épico','price':90},
        {'name':'Efeito Glow','description':'Brilho leve.','item_type':'effect','icon':'effect-glow','rarity':'raro','price':55},
        {'name':'Efeito Code Rain','description':'Código animado.','item_type':'effect','icon':'effect-code-rain','rarity':'épico','price':95},
        {'name':'Selo Python','description':'Selo Python.','item_type':'badge','icon':'badge-python','rarity':'comum','price':25},
        {'name':'Selo Web Dev','description':'Selo Web.','item_type':'badge','icon':'badge-web','rarity':'comum','price':25},
        {'name':'Selo Beta','description':'Selo beta.','item_type':'badge','icon':'badge-beta','rarity':'raro','price':45},
        {'name':'Selo Founder','description':'Selo founder.','item_type':'badge','icon':'badge-founder','rarity':'lendário','price':140},
        {'name':'Nome Glow','description':'Placa glow.','item_type':'nameplate','icon':'nameplate-glow','rarity':'raro','price':60},
        {'name':'Nome Cyber','description':'Placa cyber.','item_type':'nameplate','icon':'nameplate-cyber','rarity':'épico','price':100},
        {'name':'Tema Obsidian','description':'Tema padrão.','item_type':'theme','icon':'theme-obsidian','rarity':'comum','price':0},
        {'name':'Tema Midnight','description':'Tema escuro.','item_type':'theme','icon':'theme-midnight','rarity':'raro','price':35},
        {'name':'Tema Aurora','description':'Tema aurora.','item_type':'theme','icon':'theme-aurora','rarity':'épico','price':85},
    ]
    for data in cosmetics:
        item = StoreItem.query.filter_by(icon=data['icon']).first()
        if not item: db.session.add(StoreItem(**data))
        else:
            for k,v in data.items(): setattr(item,k,v)


def seed_achievements():
    rows = [
        ('first-login','Primeiro acesso','Entrou na Nodo pela primeira vez.','ach-login',10,0),
        ('first-post','Primeiro post','Publicou na comunidade.','ach-post',20,1),
        ('first-mission','Primeira missão','Concluiu uma missão.','ach-mission',25,1),
        ('first-friend','Primeiro amigo','Adicionou um amigo.','ach-friend',15,0),
        ('first-purchase','Primeiro item','Comprou um cosmético.','ach-shop',20,0),
        ('streak-7','7 dias','Fez streak de 7 dias.','ach-streak',50,2),
    ]
    for code,title,desc,icon,xp,coin in rows:
        a = Achievement.query.filter_by(code=code).first()
        if not a: db.session.add(Achievement(code=code,title=title,description=desc,icon=icon,xp_reward=xp,coin_reward=coin))


def award(user, code):
    if not user: return False
    ach = Achievement.query.filter_by(code=code).first()
    if not ach: return False
    if UserAchievement.query.filter_by(user_id=user.id, achievement_id=ach.id).first(): return False
    db.session.add(UserAchievement(user_id=user.id, achievement_id=ach.id))
    user.xp = (user.xp or 0) + (ach.xp_reward or 0)
    user.nodo_coins = (user.nodo_coins or 0) + (ach.coin_reward or 0)
    user.level = level_from_xp(user.xp)
    notify(user.id, f'Conquista: {ach.title}', ach.description, 'achievement')
    activity(user.id, f'{user.username} desbloqueou {ach.title}', 'achievement')
    return True


def seed_if_empty():
    if Mission.query.count() == 0:
        db.session.add_all([
            Mission(title='Primeiro script Python', description='Explique como criaria um script Python que imprime uma mensagem no terminal.', category='Python', difficulty='iniciante', xp_reward=30, coin_reward=1),
            Mission(title='Página HTML pessoal', description='Explique quais tags HTML usaria para criar uma página com nome, descrição e links.', category='Web', difficulty='iniciante', xp_reward=35, coin_reward=1),
            Mission(title='GitHub básico', description='Explique o passo a passo para criar um repositório e enviar um projeto usando Git.', category='Dev', difficulty='iniciante', xp_reward=45, coin_reward=1),
            Mission(title='Segurança de conta', description='Explique pelo menos 5 formas de proteger uma conta online.', category='Cyber ético', difficulty='iniciante', xp_reward=50, coin_reward=1),
            Mission(title='XSS na defesa', description='Explique o que é XSS e como prevenir.', category='Cyber ético', difficulty='intermediário', xp_reward=65, coin_reward=2),
        ])
    if Course.query.count() == 0:
        db.session.add_all([
            Course(title='Fundamentos de Programação', description='Lógica, variáveis, funções, listas e pequenos projetos.', category='Programação', level='iniciante'),
            Course(title='Web do Zero', description='HTML, CSS, JavaScript e deploy.', category='Web', level='iniciante'),
            Course(title='Python para Projetos', description='Scripts, APIs e automações.', category='Python', level='intermediário'),
            Course(title='Cyber Ético para Devs', description='Autenticação, headers e APIs.', category='Cyber ético', level='intermediário'),
        ])
    seed_store_items(); seed_achievements(); db.session.commit()

@app.before_request
def ensure_db_ready_once():
    if not getattr(app, '_nodo_db_ready', False):
        with app.app_context(): run_light_migrations(); seed_if_empty()
        app._nodo_db_ready = True

# ---------- health/auth/profile ----------

@app.get('/api/health')
def health():
    warnings = []
    if not os.getenv('JWT_SECRET') or os.getenv('JWT_SECRET') in {'dev-secret','troque_esse_jwt'}: warnings.append('JWT_SECRET fraco ou não configurado')
    if not os.getenv('SECRET_KEY') or os.getenv('SECRET_KEY') in {'dev','dev-local-only','troque_essa_chave'}: warnings.append('SECRET_KEY fraco ou não configurado')
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite') and os.getenv('RENDER'): warnings.append('SQLite em produção pode perder dados')
    return {'ok': True, 'version': '3.4', 'warnings': warnings}

@app.post('/api/auth/register')
def register():
    limited = require_rate('register', 8, 300)
    if limited: return limited
    d = request.json or {}
    username = clean_text(d.get('username'), 80)
    email = clean_text(d.get('email'), 180).lower()
    password = d.get('password') or ''
    if len(username) < 3: return jsonify({'error': 'Nome precisa ter pelo menos 3 caracteres'}), 400
    if '@' not in email or len(email) < 6: return jsonify({'error': 'Email inválido'}), 400
    if len(password) < 8: return jsonify({'error': 'Senha precisa ter pelo menos 8 caracteres'}), 400
    if email == 'demo@nodo.com': return jsonify({'error': 'Conta demo desativada.'}), 403
    if User.query.filter_by(email=email).first(): return jsonify({'error': 'Email já cadastrado'}), 400
    u = User(username=username, email=email, password_hash=hash_password(password), nodo_coins=2, is_admin=is_admin_email(email))
    db.session.add(u); db.session.commit(); award(u, 'first-login'); db.session.commit()
    return {'token': make_token(u.id), 'user': user_private(u)}

@app.post('/api/auth/login')
def login():
    limited = require_rate('login', 12, 300)
    if limited: return limited
    d = request.json or {}
    email = clean_text(d.get('email'), 180).lower()
    if email == 'demo@nodo.com': return jsonify({'error': 'Conta demo desativada.'}), 403
    u = User.query.filter_by(email=email).first()
    if not u or not verify_password(d.get('password') or '', u.password_hash): return jsonify({'error': 'Email ou senha inválidos'}), 401
    if getattr(u, 'is_banned', False): return jsonify({'error': 'Conta bloqueada'}), 403
    sync_admin_flag(u); award(u, 'first-login'); db.session.commit()
    return {'token': make_token(u.id), 'user': user_private(u)}

@app.get('/api/me')
@require_auth
def me(): return {'user': user_private(sync_admin_flag(User.query.get_or_404(request.user_id)))}

@app.put('/api/me')
@require_auth
def update_me():
    u = User.query.get_or_404(request.user_id); d = request.json or {}
    if d.get('username') and len(clean_text(d['username'], 80)) >= 3: u.username = clean_text(d['username'], 80)
    if d.get('email') and '@' in d['email']:
        email = clean_text(d['email'], 180).lower()
        if User.query.filter(User.email == email, User.id != u.id).first(): return jsonify({'error': 'Esse email já está em uso'}), 400
        u.email = email
    if 'phone' in d: u.phone = clean_text(d.get('phone'), 30)
    if 'bio' in d: u.bio = clean_text(d.get('bio'), 500)
    if 'avatar' in d:
        av = d.get('avatar') or '👨‍💻'
        if len(av) > 250000: return jsonify({'error': 'Imagem muito pesada'}), 400
        u.avatar = av
    db.session.commit(); sync_admin_flag(u); return {'user': user_private(u)}

@app.put('/api/me/password')
@require_auth
def update_password():
    limited = require_rate('password', 8, 300)
    if limited: return limited
    u = User.query.get_or_404(request.user_id); d = request.json or {}
    if not verify_password(d.get('current_password') or '', u.password_hash): return jsonify({'error': 'Senha atual incorreta'}), 400
    if len(d.get('new_password') or '') < 8: return jsonify({'error': 'Nova senha precisa ter pelo menos 8 caracteres'}), 400
    u.password_hash = hash_password(d['new_password']); db.session.commit(); return {'message': 'Senha alterada'}

@app.post('/api/me/equip')
@require_auth
def equip_cosmetic():
    u = User.query.get_or_404(request.user_id); d = request.json or {}; slot = clean_text(d.get('slot'), 30).lower()
    allowed = {'frame':'equipped_frame','banner':'equipped_banner','effect':'equipped_effect','badge':'equipped_badge','theme':'equipped_theme','nameplate':'nameplate'}
    if slot not in allowed: return jsonify({'error': 'Tipo inválido'}), 400
    if d.get('clear'):
        setattr(u, allowed[slot], 'theme-obsidian' if slot == 'theme' else ''); db.session.commit(); return {'message': 'Atualizado', 'user': user_private(u)}
    item = StoreItem.query.get(d.get('item_id')) if d.get('item_id') else StoreItem.query.filter_by(icon=clean_text(d.get('icon'), 80)).first()
    if not item: return jsonify({'error': 'Item não encontrado'}), 404
    if item.item_type != slot: return jsonify({'error': 'Categoria incorreta'}), 400
    owned = Purchase.query.filter_by(user_id=u.id, item_id=item.id).first()
    if not owned and (item.price or 0) > 0: return jsonify({'error': 'Você ainda não comprou esse item'}), 403
    setattr(u, allowed[slot], item.icon); db.session.commit(); return {'message': 'Equipado', 'user': user_private(u)}

# ---------- dashboard social ----------

@app.get('/api/dashboard')
@require_auth
def dashboard():
    u = User.query.get_or_404(request.user_id)
    completed = CompletedMission.query.filter_by(user_id=u.id).count(); total = Mission.query.count()
    rank_list = User.query.order_by(User.xp.desc()).all(); position = next((i+1 for i,item in enumerate(rank_list) if item.id == u.id), None)
    return {'user': user_private(u), 'stats': {'completed_missions': completed, 'total_missions': total, 'ranking_position': position, 'posts': Post.query.filter_by(user_id=u.id).count(), 'groups': len(u.groups), 'achievements': UserAchievement.query.filter_by(user_id=u.id).count()}, 'next_level_xp': u.level * 150}

@app.post('/api/streak/checkin')
@require_auth
def streak_checkin():
    u = User.query.get_or_404(request.user_id)
    if not touch_streak(u): return {'message': 'Check-in já feito.', 'user': user_private(u)}
    u.xp = (u.xp or 0) + 15; u.nodo_coins = (u.nodo_coins or 0) + 1; u.level = level_from_xp(u.xp)
    if (u.streak or 0) >= 7: award(u, 'streak-7')
    activity(u.id, f'{u.username} fez check-in', 'streak')
    db.session.commit(); return {'message': '+15 XP e +1 NC', 'user': user_private(u)}

@app.get('/api/ranking')
@require_auth
def ranking():
    users = User.query.order_by(User.xp.desc(), User.nodo_coins.desc()).limit(50).all()
    return {'ranking': [{**user_public(u), 'nodo_coins': u.nodo_coins or 0, 'streak': u.streak or 0} for u in users]}

@app.get('/api/activity')
@require_auth
def activities():
    rows = Activity.query.order_by(Activity.created_at.desc()).limit(40).all()
    return {'activity': [{'id': a.id, 'text': a.text, 'kind': a.kind, 'user': user_public(a.user) if a.user else None, 'created_at': a.created_at.isoformat()} for a in rows]}

@app.get('/api/notifications')
@require_auth
def notifications():
    rows = Notification.query.filter_by(user_id=request.user_id).order_by(Notification.created_at.desc()).limit(50).all()
    return {'notifications': [notification_payload(n) for n in rows], 'unread': Notification.query.filter_by(user_id=request.user_id, is_read=False).count()}

@app.post('/api/notifications/read')
@require_auth
def notifications_read():
    Notification.query.filter_by(user_id=request.user_id, is_read=False).update({'is_read': True}); db.session.commit(); return {'message': 'ok'}

@app.get('/api/achievements')
@require_auth
def achievements():
    owned = {ua.achievement_id for ua in UserAchievement.query.filter_by(user_id=request.user_id).all()}
    rows = Achievement.query.order_by(Achievement.id.asc()).all()
    return {'achievements': [{'id': a.id, 'code': a.code, 'title': a.title, 'description': a.description, 'icon': a.icon, 'xp_reward': a.xp_reward, 'coin_reward': a.coin_reward, 'unlocked': a.id in owned} for a in rows]}

# ---------- users/friends/groups/community ----------

@app.get('/api/users')
@require_auth
def search_users():
    q = clean_text(request.args.get('q'), 80)
    query = User.query.filter_by(is_banned=False)
    if q: query = query.filter(User.username.ilike(f'%{q}%'))
    return {'users': [user_public(u) for u in query.limit(30).all() if u.id != request.user_id]}

@app.post('/api/friends/<int:user_id>')
@require_auth
def add_friend(user_id):
    if user_id == request.user_id: return jsonify({'error': 'Você não pode adicionar você mesmo'}), 400
    target = User.query.get(user_id)
    if not target: return jsonify({'error': 'Usuário não encontrado'}), 404
    exists = Friend.query.filter(((Friend.requester_id == request.user_id) & (Friend.addressee_id == user_id)) | ((Friend.requester_id == user_id) & (Friend.addressee_id == request.user_id))).first()
    if exists: return {'message': 'Pedido já existe'}
    me_user = User.query.get_or_404(request.user_id)
    db.session.add(Friend(requester_id=request.user_id, addressee_id=user_id, status='pending'))
    notify(user_id, 'Pedido de amizade', f'{me_user.username} quer te adicionar.', 'friend')
    db.session.commit(); return {'message': 'Pedido enviado'}

@app.post('/api/friends/<int:friend_id>/accept')
@require_auth
def accept_friend(friend_id):
    row = Friend.query.get_or_404(friend_id)
    if row.addressee_id != request.user_id: return jsonify({'error':'Sem permissão'}), 403
    row.status = 'accepted'; u = User.query.get(request.user_id); other = User.query.get(row.requester_id)
    award(u, 'first-friend'); award(other, 'first-friend'); notify(row.requester_id, 'Pedido aceito', f'{u.username} aceitou seu pedido.', 'friend')
    db.session.commit(); return {'message':'Amigo adicionado'}

@app.get('/api/friends')
@require_auth
def friends():
    rows = Friend.query.filter(((Friend.requester_id == request.user_id) | (Friend.addressee_id == request.user_id))).all()
    accepted_ids = [r.addressee_id if r.requester_id == request.user_id else r.requester_id for r in rows if r.status == 'accepted']
    pending_in = [r for r in rows if r.status == 'pending' and r.addressee_id == request.user_id]
    users = User.query.filter(User.id.in_(accepted_ids)).all() if accepted_ids else []
    return {'friends': [user_public(u) for u in users], 'pending': [{'id': r.id, 'user': user_public(User.query.get(r.requester_id)), 'created_at': r.created_at.isoformat()} for r in pending_in]}

@app.get('/api/groups')
@require_auth
def list_groups():
    gs = Group.query.order_by(Group.created_at.desc()).all()
    return {'groups': [{'id':g.id,'name':g.name,'description':g.description,'topic':g.topic,'owner_id':g.owner_id,'members_count':len(g.members),'xp':g.xp or 0,'level':g.level or 1,'is_member': any(m.id == request.user_id for m in g.members)} for g in gs]}

@app.get('/api/my-groups')
@require_auth
def my_groups():
    u = User.query.get_or_404(request.user_id)
    return {'groups': [{'id':g.id,'name':g.name,'description':g.description,'topic':g.topic,'members_count':len(g.members),'level':g.level or 1} for g in u.groups]}

@app.post('/api/groups')
@require_auth
def create_group():
    d = request.json or {}; name = clean_text(d.get('name'), 120)
    if len(name) < 3: return jsonify({'error': 'Nome do Nodo muito curto'}), 400
    u = User.query.get_or_404(request.user_id)
    g = Group(name=name, description=clean_text(d.get('description'), 400), topic=clean_text(d.get('topic') or 'Programação', 80), owner_id=u.id, members=[u])
    db.session.add(g); activity(u.id, f'{u.username} criou o Nodo {name}', 'group'); db.session.commit(); return {'message': 'Nodo criado', 'group_id': g.id}

@app.post('/api/groups/<int:gid>/join')
@require_auth
def join_group(gid):
    g = Group.query.get_or_404(gid); u = User.query.get_or_404(request.user_id)
    if u not in g.members:
        g.members.append(u); g.xp = (g.xp or 0) + 10; g.level = group_level_from_xp(g.xp); activity(u.id, f'{u.username} entrou em {g.name}', 'group'); db.session.commit()
    return {'message': 'Você entrou no Nodo'}

@app.get('/api/posts')
@require_auth
def list_posts():
    ps = Post.query.order_by(Post.created_at.desc()).limit(50).all()
    return {'posts': [post_payload(p, request.user_id) for p in ps]}

@app.post('/api/posts')
@require_auth
def create_post():
    limited = require_rate('post', 20, 60)
    if limited: return limited
    c = clean_text((request.json or {}).get('content'), 1000)
    if len(c) < 2: return jsonify({'error': 'Digite algo'}), 400
    u = User.query.get_or_404(request.user_id)
    p = Post(content=c, user_id=u.id); db.session.add(p); activity(u.id, f'{u.username} publicou na comunidade', 'post'); db.session.commit(); award(u, 'first-post'); db.session.commit()
    return {'message': 'Publicado', 'post': post_payload(p, request.user_id)}

@app.post('/api/posts/<int:post_id>/like')
@require_auth
def like_post(post_id):
    p = Post.query.get_or_404(post_id)
    existing = PostLike.query.filter_by(post_id=p.id, user_id=request.user_id).first()
    if existing: db.session.delete(existing); db.session.commit(); return {'liked': False, 'post': post_payload(p, request.user_id)}
    db.session.add(PostLike(post_id=p.id, user_id=request.user_id))
    if p.user_id != request.user_id: notify(p.user_id, 'Curtida', 'Alguém curtiu seu post.', 'like')
    db.session.commit(); return {'liked': True, 'post': post_payload(p, request.user_id)}

@app.post('/api/posts/<int:post_id>/comments')
@require_auth
def comment_post(post_id):
    limited = require_rate('comment', 30, 60)
    if limited: return limited
    p = Post.query.get_or_404(post_id); c = clean_text((request.json or {}).get('content'), 700)
    if len(c) < 1: return jsonify({'error': 'Comentário vazio'}), 400
    u = User.query.get_or_404(request.user_id); db.session.add(PostComment(post_id=p.id, user_id=u.id, content=c))
    if p.user_id != u.id: notify(p.user_id, 'Comentário', f'{u.username} comentou seu post.', 'comment')
    db.session.commit(); return {'message':'Comentado', 'post': post_payload(p, request.user_id)}

@app.post('/api/reports')
@require_auth
def create_report():
    d = request.json or {}; target_type = clean_text(d.get('target_type'), 40); target_id = int(d.get('target_id') or 0); reason = clean_text(d.get('reason'), 400)
    if target_type not in {'post','user','group'} or target_id <= 0: return jsonify({'error': 'Denúncia inválida'}), 400
    db.session.add(Report(reporter_id=request.user_id, target_type=target_type, target_id=target_id, reason=reason)); db.session.commit(); return {'message': 'Denúncia enviada'}

# ---------- missions/courses/store/customize ----------

@app.get('/api/missions')
@require_auth
def missions():
    done = {c.mission_id for c in CompletedMission.query.filter_by(user_id=request.user_id).all()}; ms = Mission.query.order_by(Mission.id.asc()).all()
    return {'missions': [{'id':m.id,'title':m.title,'description':m.description,'category':m.category,'difficulty':m.difficulty or 'iniciante','xp_reward':m.xp_reward or 0,'coin_reward':m.coin_reward or 0,'completed':m.id in done} for m in ms]}

@app.post('/api/missions/<int:mid>/submit')
@require_auth
def submit_mission(mid):
    m = Mission.query.get_or_404(mid); ans = clean_text((request.json or {}).get('answer'), 1200)
    if len(ans) < 20: return jsonify({'error': 'Resposta muito curta.'}), 400
    if CompletedMission.query.filter_by(user_id=request.user_id, mission_id=mid).first(): return jsonify({'error': 'Missão já concluída'}), 400
    u = User.query.get_or_404(request.user_id); u.xp = (u.xp or 0) + (m.xp_reward or 0); u.nodo_coins = (u.nodo_coins or 0) + (m.coin_reward or 0); u.level = level_from_xp(u.xp); touch_streak(u)
    db.session.add(CompletedMission(user_id=u.id, mission_id=m.id, answer=ans)); activity(u.id, f'{u.username} completou uma missão', 'mission'); award(u, 'first-mission'); db.session.commit()
    return {'message': f'+{m.xp_reward} XP e +{m.coin_reward} NC', 'user': user_private(u)}

@app.get('/api/courses')
@require_auth
def courses():
    rows = Course.query.order_by(Course.id.asc()).all(); return {'courses': [{'id':c.id,'title':c.title,'description':c.description,'category':c.category,'level':c.level} for c in rows]}

@app.get('/api/store')
@require_auth
def store():
    owned = {p.item_id for p in Purchase.query.filter_by(user_id=request.user_id).all()}; items = StoreItem.query.order_by(StoreItem.price.asc(), StoreItem.id.asc()).all()
    return {'items': [store_item_payload(i, owned) for i in items]}

@app.post('/api/store/<int:item_id>/purchase')
@require_auth
def purchase(item_id):
    u = User.query.get_or_404(request.user_id); item = StoreItem.query.get_or_404(item_id)
    if Purchase.query.filter_by(user_id=u.id, item_id=item.id).first(): return jsonify({'error': 'Você já tem esse item'}), 400
    if (u.nodo_coins or 0) < (item.price or 0): return jsonify({'error': 'NC insuficiente'}), 400
    u.nodo_coins -= item.price or 0; db.session.add(Purchase(user_id=u.id, item_id=item.id)); activity(u.id, f'{u.username} comprou {item.name}', 'store'); db.session.commit(); award(u, 'first-purchase'); db.session.commit()
    return {'message': 'Comprado', 'user': user_private(u)}

# ---------- admin ----------

@app.get('/api/admin/overview')
@require_admin
def admin_overview():
    users = User.query.order_by(User.created_at.desc()).limit(120).all(); posts = Post.query.order_by(Post.created_at.desc()).limit(100).all(); groups = Group.query.order_by(Group.created_at.desc()).limit(100).all(); items = StoreItem.query.order_by(StoreItem.id.desc()).limit(150).all(); missions_rows = Mission.query.order_by(Mission.id.desc()).limit(150).all(); reports = Report.query.order_by(Report.created_at.desc()).limit(80).all()
    return {'summary': {'users':User.query.count(),'missions':Mission.query.count(),'posts':Post.query.count(),'groups':Group.query.count(),'courses':Course.query.count(),'store_items':StoreItem.query.count(),'reports':Report.query.filter_by(status='open').count()}, 'users':[user_private(sync_admin_flag(u)) for u in users], 'posts':[post_payload(p, request.user_id) for p in posts], 'groups':[{'id':g.id,'name':g.name,'topic':g.topic,'description':g.description,'members_count':len(g.members),'level':g.level or 1} for g in groups], 'store_items':[store_item_payload(i) for i in items], 'missions':[{'id':m.id,'title':m.title,'category':m.category,'difficulty':m.difficulty,'xp_reward':m.xp_reward,'coin_reward':m.coin_reward} for m in missions_rows], 'reports':[{'id':r.id,'target_type':r.target_type,'target_id':r.target_id,'reason':r.reason,'status':r.status,'created_at':r.created_at.isoformat()} for r in reports]}

@app.patch('/api/admin/users/<int:user_id>')
@require_admin
def admin_update_user(user_id):
    u = User.query.get_or_404(user_id); d = request.json or {}
    if 'is_admin' in d: u.is_admin = bool(d['is_admin']) or is_admin_email(u.email)
    if 'is_banned' in d and u.id != request.user_id: u.is_banned = bool(d['is_banned'])
    if 'nodo_coins' in d: u.nodo_coins = max(0, int(d.get('nodo_coins') or 0))
    if 'xp' in d: u.xp = max(0, int(d.get('xp') or 0)); u.level = level_from_xp(u.xp)
    if 'username' in d and len(clean_text(d.get('username'), 80)) >= 3: u.username = clean_text(d.get('username'), 80)
    db.session.commit(); return {'message': 'Usuário atualizado', 'user': user_private(u)}

@app.post('/api/admin/missions')
@require_admin
def admin_create_mission():
    d = request.json or {}; title = clean_text(d.get('title'), 160); description = clean_text(d.get('description'), 600)
    if len(title)<3 or len(description)<10: return jsonify({'error':'Título/descrição muito curtos'}), 400
    m = Mission(title=title, description=description, category=clean_text(d.get('category') or 'Programação', 80), difficulty=clean_text(d.get('difficulty') or 'iniciante', 30), xp_reward=max(0,min(int(d.get('xp_reward') or 30),300)), coin_reward=max(0,min(int(d.get('coin_reward') or 1),3)))
    db.session.add(m); db.session.commit(); return {'message':'Missão criada', 'mission_id':m.id}

@app.delete('/api/admin/missions/<int:mission_id>')
@require_admin
def admin_delete_mission(mission_id):
    m = Mission.query.get_or_404(mission_id); CompletedMission.query.filter_by(mission_id=m.id).delete(); db.session.delete(m); db.session.commit(); return {'message':'Missão apagada'}

@app.post('/api/admin/store')
@require_admin
def admin_create_store_item():
    d = request.json or {}; name = clean_text(d.get('name'), 120)
    if len(name)<2: return jsonify({'error':'Nome muito curto'}), 400
    item = StoreItem(name=name, description=clean_text(d.get('description'), 400), item_type=clean_text(d.get('item_type') or 'badge', 50), icon=clean_text(d.get('icon') or 'badge-founder', 80), rarity=clean_text(d.get('rarity') or 'comum', 30), price=max(0, int(d.get('price') or 25)))
    db.session.add(item); db.session.commit(); return {'message':'Item criado', 'item_id':item.id}

@app.delete('/api/admin/store/<int:item_id>')
@require_admin
def admin_delete_store_item(item_id):
    item = StoreItem.query.get_or_404(item_id); Purchase.query.filter_by(item_id=item.id).delete(); db.session.delete(item); db.session.commit(); return {'message':'Item apagado'}

@app.delete('/api/admin/posts/<int:post_id>')
@require_admin
def admin_delete_post(post_id):
    p = Post.query.get_or_404(post_id); PostLike.query.filter_by(post_id=p.id).delete(); PostComment.query.filter_by(post_id=p.id).delete(); db.session.delete(p); db.session.commit(); return {'message':'Post apagado'}

@app.delete('/api/admin/groups/<int:group_id>')
@require_admin
def admin_delete_group(group_id):
    g = Group.query.get_or_404(group_id); ChatMessage.query.filter_by(room=f'group:{g.id}').delete(); db.session.delete(g); db.session.commit(); return {'message':'Nodo apagado'}

@app.patch('/api/admin/reports/<int:report_id>')
@require_admin
def admin_update_report(report_id):
    r = Report.query.get_or_404(report_id); r.status = clean_text((request.json or {}).get('status') or 'closed', 30); db.session.commit(); return {'message':'Denúncia atualizada'}

# ---------- chat/AI ----------

@app.get('/api/chat/history')
@require_auth
def chat_history():
    room = clean_text(request.args.get('room') or 'global', 120); ms = ChatMessage.query.filter_by(room=room).order_by(ChatMessage.created_at.desc()).limit(80).all(); ms.reverse()
    return {'messages': [{'id':m.id,'room':m.room,'content':m.content,'username':m.username,'user_id':m.user_id,'created_at':m.created_at.isoformat()} for m in ms]}

@app.post('/api/chat/message')
@require_auth
def chat_send_message():
    limited = require_rate('chat', 45, 60)
    if limited: return limited
    d = request.json or {}; room = clean_text(d.get('room') or 'global', 120); content = clean_text(d.get('content'), 1000)
    if len(content)<1: return jsonify({'error':'Mensagem vazia'}), 400
    u = User.query.get_or_404(request.user_id); msg = ChatMessage(room=room, content=content, username=u.username, user_id=u.id); db.session.add(msg); db.session.commit()
    payload = {'id':msg.id,'room':msg.room,'content':msg.content,'username':msg.username,'user_id':msg.user_id,'created_at':msg.created_at.isoformat()}
    try: socketio.emit('message', payload, to=room)
    except Exception: pass
    return {'message': payload}

@app.post('/api/ai')
@require_auth
def ai_chat():
    limited = require_rate('ai', 20, 300)
    if limited: return limited
    prompt = clean_text((request.json or {}).get('message'), 2500); key = os.getenv('OPENAI_API_KEY')
    if not prompt: return jsonify({'error':'Mensagem vazia'}), 400
    if not key: return {'reply':'Nodo AI ainda não está configurada.'}
    try:
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(model='gpt-4.1-mini', messages=[{'role':'system','content':'Você é a Nodo AI. Ajude com programação, projetos, estudo e segurança ética. Recuse invasão, golpes, malware e crime.'},{'role':'user','content':prompt}], temperature=.4)
        return {'reply': resp.choices[0].message.content}
    except Exception:
        return jsonify({'error':'Erro na Nodo AI'}), 500


def socket_user_from_data(data):
    token = (data or {}).get('token') or ''
    try: return User.query.get(decode_token(token)['user_id'])
    except Exception: return None

@socketio.on('join')
def on_join(data):
    u = socket_user_from_data(data)
    if not u: emit('system', {'message':'Token inválido'}, to=request.sid); return
    room = clean_text((data or {}).get('room') or 'global', 120); join_room(room); emit('system', {'message': f'Entrou em {room}'}, to=request.sid)

@socketio.on('message')
def on_message(data):
    room = clean_text((data or {}).get('room') or 'global', 120); content = clean_text((data or {}).get('content'), 1000)
    u = socket_user_from_data(data)
    if not u or not content: return
    msg = ChatMessage(room=room, content=content, username=u.username, user_id=u.id); db.session.add(msg); db.session.commit()
    emit('message', {'id':msg.id,'room':room,'content':msg.content,'username':u.username,'user_id':u.id,'created_at':msg.created_at.isoformat()}, to=room)

if __name__ == '__main__':
    with app.app_context(): run_light_migrations(); seed_if_empty()
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG') == '1')
