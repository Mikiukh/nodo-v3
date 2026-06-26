import os
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
    db,
    User,
    Friend,
    Group,
    Post,
    ChatMessage,
    Mission,
    CompletedMission,
    Course,
    StoreItem,
    Purchase,
)
from security import hash_password, verify_password, make_token, decode_token, require_auth


# ---------- app/config ----------

def normalize_database_url(url: str) -> str:
    if url and url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    return url


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_url(os.getenv('DATABASE_URL', 'sqlite:///nodo.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

client_origin = os.getenv('CLIENT_ORIGIN', 'http://localhost:5173')
allowed_origins = [o.strip() for o in client_origin.split(',') if o.strip()]
CORS(
    app,
    resources={
        r'/api/*': {
            'origins': allowed_origins or ['http://localhost:5173'],
            'methods': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
            'allow_headers': ['Content-Type', 'Authorization'],
        }
    },
    supports_credentials=True,
)
socketio = SocketIO(app, cors_allowed_origins=allowed_origins or ['http://localhost:5173'], async_mode='threading')
db.init_app(app)


# ---------- helpers/serializers ----------

def level_from_xp(xp: int) -> int:
    return max(1, int(xp or 0) // 150 + 1)


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
    return {
        'id': i.id,
        'name': i.name,
        'description': i.description or '',
        'item_type': i.item_type or 'badge',
        'icon': i.icon or 'badge-founder',
        'rarity': i.rarity or 'comum',
        'price': i.price or 0,
        'owned': i.id in owned_ids,
    }


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
    raw = os.getenv('ADMIN_EMAILS') or os.getenv('ADMIN_EMAIL') or 'pedwyz73@gmail.com'
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


# ---------- migrations/seed ----------

def add_column_if_missing(table_name, column_name, definition):
    inspector = inspect(db.engine)
    cols = {c['name'] for c in inspector.get_columns(table_name)}
    if column_name in cols:
        return
    table_sql = '"user"' if table_name == 'user' else table_name
    db.session.execute(text(f'ALTER TABLE {table_sql} ADD COLUMN {column_name} {definition}'))


def run_light_migrations():
    """Simple safe upgrades for the current MVP.

    Keeps older SQLite/Postgres databases alive when V3.3 adds cosmetics/admin fields.
    For a larger production version, replace this with Alembic migrations.
    """
    db.create_all()

    user_additions = {
        'nodo_coins': 'INTEGER DEFAULT 2',
        'streak': 'INTEGER DEFAULT 0',
        'last_streak_date': 'DATE',
        'is_admin': 'BOOLEAN DEFAULT FALSE',
        'equipped_frame': "VARCHAR(80) DEFAULT ''",
        'equipped_banner': "VARCHAR(80) DEFAULT ''",
        'equipped_effect': "VARCHAR(80) DEFAULT ''",
        'equipped_badge': "VARCHAR(80) DEFAULT ''",
        'equipped_theme': "VARCHAR(80) DEFAULT 'theme-obsidian'",
        'nameplate': "VARCHAR(80) DEFAULT ''",
    }
    for col, definition in user_additions.items():
        add_column_if_missing('user', col, definition)

    mission_additions = {
        'difficulty': "VARCHAR(30) DEFAULT 'iniciante'",
        'coin_reward': 'INTEGER DEFAULT 1',
        'created_at': 'TIMESTAMP',
    }
    for col, definition in mission_additions.items():
        add_column_if_missing('mission', col, definition)

    store_additions = {
        'rarity': "VARCHAR(30) DEFAULT 'comum'",
    }
    for col, definition in store_additions.items():
        add_column_if_missing('store_item', col, definition)

    db.session.commit()


def seed_store_items():
    cosmetics = [
        # frame
        {'name': 'Moldura Carbon', 'description': 'Borda escura para o avatar.', 'item_type': 'frame', 'icon': 'frame-carbon', 'rarity': 'comum', 'price': 18},
        {'name': 'Moldura Neon', 'description': 'Borda neon para o avatar.', 'item_type': 'frame', 'icon': 'frame-neon', 'rarity': 'raro', 'price': 45},
        {'name': 'Moldura Glitch', 'description': 'Borda com visual glitch.', 'item_type': 'frame', 'icon': 'frame-glitch', 'rarity': 'épico', 'price': 80},
        {'name': 'Moldura Founder', 'description': 'Borda especial de fundador.', 'item_type': 'frame', 'icon': 'frame-founder', 'rarity': 'lendário', 'price': 120},
        # banner
        {'name': 'Banner Obsidian', 'description': 'Banner escuro para perfil.', 'item_type': 'banner', 'icon': 'banner-obsidian', 'rarity': 'comum', 'price': 20},
        {'name': 'Banner Aurora', 'description': 'Banner com brilho suave.', 'item_type': 'banner', 'icon': 'banner-aurora', 'rarity': 'raro', 'price': 50},
        {'name': 'Banner Cyber', 'description': 'Banner estilo cyber.', 'item_type': 'banner', 'icon': 'banner-cyber', 'rarity': 'épico', 'price': 90},
        # effect
        {'name': 'Efeito Glow', 'description': 'Brilho leve no perfil.', 'item_type': 'effect', 'icon': 'effect-glow', 'rarity': 'raro', 'price': 55},
        {'name': 'Efeito Code Rain', 'description': 'Detalhe visual de código.', 'item_type': 'effect', 'icon': 'effect-code-rain', 'rarity': 'épico', 'price': 95},
        # badge
        {'name': 'Selo Python', 'description': 'Selo de estudos em Python.', 'item_type': 'badge', 'icon': 'badge-python', 'rarity': 'comum', 'price': 25},
        {'name': 'Selo Web Dev', 'description': 'Selo de desenvolvimento web.', 'item_type': 'badge', 'icon': 'badge-web', 'rarity': 'comum', 'price': 25},
        {'name': 'Selo Beta', 'description': 'Selo de testador beta.', 'item_type': 'badge', 'icon': 'badge-beta', 'rarity': 'raro', 'price': 45},
        {'name': 'Selo Founder', 'description': 'Selo especial de fundador.', 'item_type': 'badge', 'icon': 'badge-founder', 'rarity': 'lendário', 'price': 140},
        # nameplate/theme
        {'name': 'Nome Glow', 'description': 'Placa com brilho no nome.', 'item_type': 'nameplate', 'icon': 'nameplate-glow', 'rarity': 'raro', 'price': 60},
        {'name': 'Nome Cyber', 'description': 'Placa cyber para o nome.', 'item_type': 'nameplate', 'icon': 'nameplate-cyber', 'rarity': 'épico', 'price': 100},
        {'name': 'Tema Obsidian', 'description': 'Tema escuro do perfil.', 'item_type': 'theme', 'icon': 'theme-obsidian', 'rarity': 'comum', 'price': 0},
        {'name': 'Tema Midnight', 'description': 'Tema premium escuro.', 'item_type': 'theme', 'icon': 'theme-midnight', 'rarity': 'raro', 'price': 35},
        {'name': 'Tema Aurora', 'description': 'Tema com contraste suave.', 'item_type': 'theme', 'icon': 'theme-aurora', 'rarity': 'épico', 'price': 85},
    ]
    for data in cosmetics:
        item = StoreItem.query.filter_by(icon=data['icon']).first()
        if not item:
            db.session.add(StoreItem(**data))
        else:
            # Mantém o catálogo limpo mesmo após upgrades antigos.
            for k, v in data.items():
                setattr(item, k, v)


def seed_if_empty():
    if Mission.query.count() == 0:
        db.session.add_all([
            Mission(title='Primeiro script Python', description='Explique como criaria um script Python que imprime uma mensagem no terminal.', category='Python', difficulty='iniciante', xp_reward=30, coin_reward=1),
            Mission(title='Página HTML pessoal', description='Explique quais tags HTML usaria para criar uma página com nome, descrição e links.', category='Web', difficulty='iniciante', xp_reward=35, coin_reward=1),
            Mission(title='GitHub básico', description='Explique o passo a passo para criar um repositório e enviar um projeto usando Git.', category='Dev', difficulty='iniciante', xp_reward=45, coin_reward=1),
            Mission(title='Segurança de conta', description='Explique pelo menos 5 formas de proteger uma conta online.', category='Cyber ético', difficulty='iniciante', xp_reward=50, coin_reward=1),
            Mission(title='XSS na defesa', description='Explique o que é XSS e como um desenvolvedor pode prevenir esse tipo de falha.', category='Cyber ético', difficulty='intermediário', xp_reward=65, coin_reward=2),
            Mission(title='API protegida', description='Explique por que uma rota privada deve exigir autenticação.', category='API', difficulty='intermediário', xp_reward=75, coin_reward=2),
        ])
    if Course.query.count() == 0:
        db.session.add_all([
            Course(title='Fundamentos de Programação', description='Lógica, variáveis, funções, listas e pequenos projetos.', category='Programação', level='iniciante'),
            Course(title='Web do Zero', description='HTML, CSS, JavaScript e deploy de páginas simples.', category='Web', level='iniciante'),
            Course(title='Python para Projetos', description='Scripts, arquivos, APIs e automações úteis.', category='Python', level='intermediário'),
            Course(title='Cyber Ético para Devs', description='Autenticação, headers, APIs e boas práticas.', category='Cyber ético', level='intermediário'),
        ])
    seed_store_items()
    db.session.commit()


@app.before_request
def ensure_db_ready_once():
    if not getattr(app, '_nodo_db_ready', False):
        with app.app_context():
            run_light_migrations()
            seed_if_empty()
        app._nodo_db_ready = True


# ---------- health/auth/profile ----------

@app.get('/api/health')
def health():
    return {'ok': True, 'version': '3.3'}


@app.post('/api/auth/register')
def register():
    d = request.json or {}
    username = (d.get('username') or '').strip()
    email = (d.get('email') or '').strip().lower()
    password = d.get('password') or ''
    if len(username) < 3:
        return jsonify({'error': 'Nome precisa ter pelo menos 3 caracteres'}), 400
    if '@' not in email or len(email) < 6:
        return jsonify({'error': 'Email inválido'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Senha precisa ter pelo menos 8 caracteres'}), 400
    if email == 'demo@nodo.com':
        return jsonify({'error': 'Conta demo desativada. Crie sua própria conta.'}), 403
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email já cadastrado'}), 400
    is_first = User.query.count() == 0
    u = User(username=username, email=email, password_hash=hash_password(password), nodo_coins=2, is_admin=is_first or is_admin_email(email))
    db.session.add(u)
    db.session.commit()
    return {'token': make_token(u.id), 'user': user_private(u)}


@app.post('/api/auth/login')
def login():
    d = request.json or {}
    email = (d.get('email') or '').strip().lower()
    if email == 'demo@nodo.com':
        return jsonify({'error': 'Conta demo desativada. Crie sua própria conta.'}), 403
    u = User.query.filter_by(email=email).first()
    if not u or not verify_password(d.get('password') or '', u.password_hash):
        return jsonify({'error': 'Email ou senha inválidos'}), 401
    sync_admin_flag(u)
    return {'token': make_token(u.id), 'user': user_private(u)}


@app.get('/api/me')
@require_auth
def me():
    return {'user': user_private(sync_admin_flag(User.query.get_or_404(request.user_id)))}


@app.put('/api/me')
@require_auth
def update_me():
    u = User.query.get_or_404(request.user_id)
    d = request.json or {}
    if d.get('username') and len(d['username'].strip()) >= 3:
        u.username = d['username'].strip()[:80]
    if d.get('email') and '@' in d['email']:
        email = d['email'].strip().lower()
        exists = User.query.filter(User.email == email, User.id != u.id).first()
        if exists:
            return jsonify({'error': 'Esse email já está em uso'}), 400
        u.email = email
    if 'phone' in d:
        u.phone = (d.get('phone') or '')[:30]
    if 'bio' in d:
        u.bio = (d.get('bio') or '')[:500]
    if 'avatar' in d:
        av = d.get('avatar') or '👨‍💻'
        if len(av) > 250000:
            return jsonify({'error': 'Imagem muito pesada'}), 400
        u.avatar = av
    db.session.commit()
    sync_admin_flag(u)
    return {'user': user_private(u)}


@app.put('/api/me/password')
@require_auth
def update_password():
    u = User.query.get_or_404(request.user_id)
    d = request.json or {}
    if not verify_password(d.get('current_password') or '', u.password_hash):
        return jsonify({'error': 'Senha atual incorreta'}), 400
    if len(d.get('new_password') or '') < 8:
        return jsonify({'error': 'Nova senha precisa ter pelo menos 8 caracteres'}), 400
    u.password_hash = hash_password(d['new_password'])
    db.session.commit()
    return {'message': 'Senha alterada'}


@app.post('/api/me/equip')
@require_auth
def equip_cosmetic():
    u = User.query.get_or_404(request.user_id)
    d = request.json or {}
    slot = (d.get('slot') or '').strip().lower()
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

    # limpar item equipado
    if d.get('clear'):
        setattr(u, allowed[slot], 'theme-obsidian' if slot == 'theme' else '')
        db.session.commit()
        return {'message': 'Atualizado', 'user': user_private(u)}

    item = None
    if d.get('item_id'):
        item = StoreItem.query.get(d.get('item_id'))
    elif d.get('icon'):
        item = StoreItem.query.filter_by(icon=(d.get('icon') or '')[:80]).first()
    if not item:
        return jsonify({'error': 'Item não encontrado'}), 404
    if item.item_type != slot:
        return jsonify({'error': 'Esse item não pertence a essa categoria'}), 400
    owned = Purchase.query.filter_by(user_id=u.id, item_id=item.id).first()
    if not owned and (item.price or 0) > 0:
        return jsonify({'error': 'Você ainda não comprou esse item'}), 403
    setattr(u, allowed[slot], item.icon)
    db.session.commit()
    return {'message': 'Equipado', 'user': user_private(u)}


# ---------- dashboard/ranking/streak ----------

@app.get('/api/dashboard')
@require_auth
def dashboard():
    u = User.query.get_or_404(request.user_id)
    completed = CompletedMission.query.filter_by(user_id=u.id).count()
    total = Mission.query.count()
    rank_list = User.query.order_by(User.xp.desc()).all()
    position = next((i + 1 for i, item in enumerate(rank_list) if item.id == u.id), None)
    return {
        'user': user_private(u),
        'stats': {
            'completed_missions': completed,
            'total_missions': total,
            'ranking_position': position,
            'posts': Post.query.filter_by(user_id=u.id).count(),
            'groups': len(u.groups),
        },
        'next_level_xp': u.level * 150,
    }


@app.post('/api/streak/checkin')
@require_auth
def streak_checkin():
    u = User.query.get_or_404(request.user_id)
    if not touch_streak(u):
        return {'message': 'Check-in de hoje já foi feito.', 'user': user_private(u)}
    u.xp = (u.xp or 0) + 15
    u.nodo_coins = (u.nodo_coins or 0) + 1
    u.level = level_from_xp(u.xp)
    db.session.commit()
    return {'message': 'Check-in feito. +15 XP e +1 NC.', 'user': user_private(u)}


@app.get('/api/ranking')
@require_auth
def ranking():
    users = User.query.order_by(User.xp.desc(), User.nodo_coins.desc()).limit(50).all()
    return {'ranking': [{**user_public(u), 'nodo_coins': u.nodo_coins or 0, 'streak': u.streak or 0} for u in users]}


# ---------- users/friends/groups/community ----------

@app.get('/api/users')
@require_auth
def search_users():
    q = (request.args.get('q') or '').strip()
    query = User.query
    if q:
        query = query.filter(User.username.ilike(f'%{q}%'))
    return {'users': [user_public(u) for u in query.limit(30).all() if u.id != request.user_id]}


@app.post('/api/friends/<int:user_id>')
@require_auth
def add_friend(user_id):
    if user_id == request.user_id:
        return jsonify({'error': 'Você não pode adicionar você mesmo'}), 400
    if not User.query.get(user_id):
        return jsonify({'error': 'Usuário não encontrado'}), 404
    exists = Friend.query.filter(
        ((Friend.requester_id == request.user_id) & (Friend.addressee_id == user_id)) |
        ((Friend.requester_id == user_id) & (Friend.addressee_id == request.user_id))
    ).first()
    if not exists:
        db.session.add(Friend(requester_id=request.user_id, addressee_id=user_id))
        db.session.commit()
    return {'message': 'Amigo adicionado'}


@app.get('/api/friends')
@require_auth
def friends():
    rows = Friend.query.filter(
        ((Friend.requester_id == request.user_id) | (Friend.addressee_id == request.user_id)),
        Friend.status == 'accepted'
    ).all()
    ids = [r.addressee_id if r.requester_id == request.user_id else r.requester_id for r in rows]
    users = User.query.filter(User.id.in_(ids)).all() if ids else []
    return {'friends': [user_public(u) for u in users]}


@app.get('/api/groups')
@require_auth
def list_groups():
    gs = Group.query.order_by(Group.created_at.desc()).all()
    return {'groups': [{
        'id': g.id,
        'name': g.name,
        'description': g.description,
        'topic': g.topic,
        'owner_id': g.owner_id,
        'members_count': len(g.members),
        'is_member': any(m.id == request.user_id for m in g.members),
    } for g in gs]}


@app.get('/api/my-groups')
@require_auth
def my_groups():
    u = User.query.get_or_404(request.user_id)
    return {'groups': [{'id': g.id, 'name': g.name, 'description': g.description, 'topic': g.topic, 'members_count': len(g.members)} for g in u.groups]}


@app.get('/api/groups/<int:gid>')
@require_auth
def group_detail(gid):
    g = Group.query.get_or_404(gid)
    return {'group': {'id': g.id, 'name': g.name, 'description': g.description, 'topic': g.topic, 'members_count': len(g.members), 'members': [user_public(u) for u in g.members]}}


@app.post('/api/groups')
@require_auth
def create_group():
    d = request.json or {}
    name = (d.get('name') or '').strip()
    if len(name) < 3:
        return jsonify({'error': 'Nome do grupo muito curto'}), 400
    u = User.query.get_or_404(request.user_id)
    g = Group(name=name, description=(d.get('description') or '')[:400], topic=(d.get('topic') or 'Programação')[:80], owner_id=u.id, members=[u])
    db.session.add(g)
    db.session.commit()
    return {'message': 'Nodo criado', 'group_id': g.id}


@app.post('/api/groups/<int:gid>/join')
@require_auth
def join_group(gid):
    g = Group.query.get_or_404(gid)
    u = User.query.get_or_404(request.user_id)
    if u not in g.members:
        g.members.append(u)
        db.session.commit()
    return {'message': 'Você entrou no Nodo'}


@app.get('/api/posts')
@require_auth
def list_posts():
    ps = Post.query.order_by(Post.created_at.desc()).limit(50).all()
    return {'posts': [{'id': p.id, 'content': p.content, 'user': user_public(p.user), 'created_at': p.created_at.isoformat()} for p in ps]}


@app.post('/api/posts')
@require_auth
def create_post():
    c = ((request.json or {}).get('content') or '').strip()
    if len(c) < 2:
        return jsonify({'error': 'Digite algo'}), 400
    db.session.add(Post(content=c[:1000], user_id=request.user_id))
    db.session.commit()
    return {'message': 'Publicado'}


# ---------- missions/courses/store/customize ----------

@app.get('/api/missions')
@require_auth
def missions():
    done = {c.mission_id for c in CompletedMission.query.filter_by(user_id=request.user_id).all()}
    ms = Mission.query.order_by(Mission.id.asc()).all()
    return {'missions': [{
        'id': m.id,
        'title': m.title,
        'description': m.description,
        'category': m.category,
        'difficulty': m.difficulty or 'iniciante',
        'xp_reward': m.xp_reward or 0,
        'coin_reward': m.coin_reward or 0,
        'completed': m.id in done,
    } for m in ms]}


@app.post('/api/missions/<int:mid>/submit')
@require_auth
def submit_mission(mid):
    m = Mission.query.get_or_404(mid)
    ans = ((request.json or {}).get('answer') or '').strip()
    if len(ans) < 20:
        return jsonify({'error': 'Resposta muito curta. Explique melhor para ganhar XP.'}), 400
    if CompletedMission.query.filter_by(user_id=request.user_id, mission_id=mid).first():
        return jsonify({'error': 'Missão já concluída'}), 400
    u = User.query.get_or_404(request.user_id)
    u.xp = (u.xp or 0) + (m.xp_reward or 0)
    u.nodo_coins = (u.nodo_coins or 0) + (m.coin_reward or 0)
    u.level = level_from_xp(u.xp)
    touch_streak(u)
    db.session.add(CompletedMission(user_id=u.id, mission_id=m.id, answer=ans[:1200]))
    db.session.commit()
    return {'message': f'+{m.xp_reward} XP e +{m.coin_reward} NC', 'user': user_private(u)}


@app.get('/api/courses')
@require_auth
def courses():
    rows = Course.query.order_by(Course.id.asc()).all()
    return {'courses': [{'id': c.id, 'title': c.title, 'description': c.description, 'category': c.category, 'level': c.level} for c in rows]}


@app.get('/api/store')
@require_auth
def store():
    owned = {p.item_id for p in Purchase.query.filter_by(user_id=request.user_id).all()}
    items = StoreItem.query.order_by(StoreItem.price.asc(), StoreItem.id.asc()).all()
    return {'items': [store_item_payload(i, owned) for i in items]}


@app.post('/api/store/<int:item_id>/purchase')
@require_auth
def purchase(item_id):
    u = User.query.get_or_404(request.user_id)
    item = StoreItem.query.get_or_404(item_id)
    if Purchase.query.filter_by(user_id=u.id, item_id=item.id).first():
        return jsonify({'error': 'Você já tem esse item'}), 400
    if (u.nodo_coins or 0) < (item.price or 0):
        return jsonify({'error': 'NC insuficiente'}), 400
    u.nodo_coins -= item.price or 0
    db.session.add(Purchase(user_id=u.id, item_id=item.id))
    db.session.commit()
    return {'message': 'Comprado', 'user': user_private(u)}


# ---------- admin ----------

@app.get('/api/admin/summary')
@require_admin
def admin_summary():
    return {
        'users': User.query.count(),
        'missions': Mission.query.count(),
        'posts': Post.query.count(),
        'groups': Group.query.count(),
        'courses': Course.query.count(),
        'store_items': StoreItem.query.count(),
    }


@app.get('/api/admin/overview')
@require_admin
def admin_overview():
    users = User.query.order_by(User.created_at.desc()).limit(80).all()
    posts = Post.query.order_by(Post.created_at.desc()).limit(80).all()
    groups = Group.query.order_by(Group.created_at.desc()).limit(80).all()
    items = StoreItem.query.order_by(StoreItem.id.desc()).limit(120).all()
    missions_rows = Mission.query.order_by(Mission.id.desc()).limit(120).all()
    return {
        'summary': {
            'users': User.query.count(),
            'missions': Mission.query.count(),
            'posts': Post.query.count(),
            'groups': Group.query.count(),
            'courses': Course.query.count(),
            'store_items': StoreItem.query.count(),
        },
        'users': [user_private(sync_admin_flag(u)) for u in users],
        'posts': [{'id': p.id, 'content': p.content, 'user': user_public(p.user), 'created_at': p.created_at.isoformat()} for p in posts],
        'groups': [{'id': g.id, 'name': g.name, 'topic': g.topic, 'description': g.description, 'members_count': len(g.members)} for g in groups],
        'store_items': [store_item_payload(i) for i in items],
        'missions': [{'id': m.id, 'title': m.title, 'category': m.category, 'difficulty': m.difficulty, 'xp_reward': m.xp_reward, 'coin_reward': m.coin_reward} for m in missions_rows],
    }


@app.patch('/api/admin/users/<int:user_id>')
@require_admin
def admin_update_user(user_id):
    u = User.query.get_or_404(user_id)
    d = request.json or {}
    if 'is_admin' in d:
        u.is_admin = bool(d['is_admin']) or is_admin_email(u.email)
    if 'nodo_coins' in d:
        u.nodo_coins = max(0, int(d.get('nodo_coins') or 0))
    if 'xp' in d:
        u.xp = max(0, int(d.get('xp') or 0))
        u.level = level_from_xp(u.xp)
    if 'username' in d and len((d.get('username') or '').strip()) >= 3:
        u.username = d['username'].strip()[:80]
    db.session.commit()
    return {'message': 'Usuário atualizado', 'user': user_private(u)}


@app.post('/api/admin/missions')
@require_admin
def admin_create_mission():
    d = request.json or {}
    title = (d.get('title') or '').strip()
    description = (d.get('description') or '').strip()
    if len(title) < 3 or len(description) < 10:
        return jsonify({'error': 'Título/descrição muito curtos'}), 400
    m = Mission(
        title=title[:160],
        description=description[:600],
        category=(d.get('category') or 'Programação')[:80],
        difficulty=(d.get('difficulty') or 'iniciante')[:30],
        xp_reward=max(0, min(int(d.get('xp_reward') or 30), 300)),
        coin_reward=max(0, min(int(d.get('coin_reward') or 1), 3)),
    )
    db.session.add(m)
    db.session.commit()
    return {'message': 'Missão criada', 'mission_id': m.id}


@app.delete('/api/admin/missions/<int:mission_id>')
@require_admin
def admin_delete_mission(mission_id):
    m = Mission.query.get_or_404(mission_id)
    CompletedMission.query.filter_by(mission_id=m.id).delete()
    db.session.delete(m)
    db.session.commit()
    return {'message': 'Missão apagada'}


@app.post('/api/admin/store')
@require_admin
def admin_create_store_item():
    d = request.json or {}
    name = (d.get('name') or '').strip()
    if len(name) < 2:
        return jsonify({'error': 'Nome muito curto'}), 400
    item = StoreItem(
        name=name[:120],
        description=(d.get('description') or '')[:400],
        item_type=(d.get('item_type') or 'badge')[:50],
        icon=(d.get('icon') or 'badge-founder')[:80],
        rarity=(d.get('rarity') or 'comum')[:30],
        price=max(0, int(d.get('price') or 25)),
    )
    db.session.add(item)
    db.session.commit()
    return {'message': 'Item criado', 'item_id': item.id}


@app.delete('/api/admin/store/<int:item_id>')
@require_admin
def admin_delete_store_item(item_id):
    item = StoreItem.query.get_or_404(item_id)
    Purchase.query.filter_by(item_id=item.id).delete()
    db.session.delete(item)
    db.session.commit()
    return {'message': 'Item apagado'}


@app.delete('/api/admin/posts/<int:post_id>')
@require_admin
def admin_delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return {'message': 'Post apagado'}


@app.delete('/api/admin/groups/<int:group_id>')
@require_admin
def admin_delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    ChatMessage.query.filter_by(room=f'group:{group.id}').delete()
    db.session.delete(group)
    db.session.commit()
    return {'message': 'Nodo apagado'}


# ---------- chat/AI ----------

@app.get('/api/chat/history')
@require_auth
def chat_history():
    room = request.args.get('room', 'global')[:120]
    ms = ChatMessage.query.filter_by(room=room).order_by(ChatMessage.created_at.desc()).limit(80).all()
    ms.reverse()
    return {'messages': [{'id': m.id, 'room': m.room, 'content': m.content, 'username': m.username, 'user_id': m.user_id, 'created_at': m.created_at.isoformat()} for m in ms]}


@app.post('/api/chat/message')
@require_auth
def chat_send_message():
    d = request.json or {}
    room = (d.get('room') or 'global')[:120]
    content = (d.get('content') or '').strip()
    if len(content) < 1:
        return jsonify({'error': 'Mensagem vazia'}), 400
    u = User.query.get_or_404(request.user_id)
    msg = ChatMessage(room=room, content=content[:1000], username=u.username, user_id=u.id)
    db.session.add(msg)
    db.session.commit()
    payload = {'id': msg.id, 'room': msg.room, 'content': msg.content, 'username': msg.username, 'user_id': msg.user_id, 'created_at': msg.created_at.isoformat()}
    try:
        socketio.emit('message', payload, to=room)
    except Exception:
        pass
    return {'message': payload}


@app.post('/api/ai')
@require_auth
def ai_chat():
    prompt = ((request.json or {}).get('message') or '').strip()
    key = os.getenv('OPENAI_API_KEY')
    if not prompt:
        return jsonify({'error': 'Mensagem vazia'}), 400
    if not key:
        return {'reply': 'Nodo AI ainda não está configurada.'}
    try:
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model='gpt-4.1-mini',
            messages=[
                {'role': 'system', 'content': 'Você é a Nodo AI. Ajude com programação, projetos, estudo e segurança ética. Não ajude com invasão, golpes, malware ou crime.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=.4,
        )
        return {'reply': resp.choices[0].message.content}
    except Exception as e:
        return jsonify({'error': 'Erro na Nodo AI', 'detail': str(e)}), 500


def socket_user_from_data(data):
    token = (data or {}).get('token') or ''
    try:
        user_id = decode_token(token)['user_id']
        return User.query.get(user_id)
    except Exception:
        return None


@socketio.on('join')
def on_join(data):
    room = ((data or {}).get('room') or 'global')[:120]
    join_room(room)
    emit('system', {'message': f'Entrou na sala {room}'}, to=request.sid)


@socketio.on('message')
def on_message(data):
    room = ((data or {}).get('room') or 'global')[:120]
    content = ((data or {}).get('content') or '').strip()
    if not content:
        return
    u = socket_user_from_data(data)
    username = u.username if u else 'Anônimo'
    user_id = u.id if u else None
    msg = ChatMessage(room=room, content=content[:1000], username=username, user_id=user_id)
    db.session.add(msg)
    db.session.commit()
    emit('message', {'id': msg.id, 'room': room, 'content': msg.content, 'username': username, 'user_id': user_id, 'created_at': msg.created_at.isoformat()}, to=room)


if __name__ == '__main__':
    with app.app_context():
        run_light_migrations()
        seed_if_empty()
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
