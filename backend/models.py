from datetime import datetime
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()

group_members = db.Table(
    'group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id')),
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30), default='')
    bio = db.Column(db.String(500), default='')
    avatar = db.Column(db.Text, default='👨‍💻')
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    nodo_coins = db.Column(db.Integer, default=5)
    streak = db.Column(db.Integer, default=0)
    last_streak_date = db.Column(db.Date, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Friend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    addressee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='accepted')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(400), default='')
    topic = db.Column(db.String(80), default='Programação')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    members = db.relationship('User', secondary=group_members, backref='groups')


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(1000), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room = db.Column(db.String(120), default='global')
    content = db.Column(db.String(1000), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(120), default='Sistema')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Mission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(600), nullable=False)
    category = db.Column(db.String(80), default='Programação')
    difficulty = db.Column(db.String(30), default='iniciante')
    xp_reward = db.Column(db.Integer, default=50)
    coin_reward = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CompletedMission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    answer = db.Column(db.String(1200), default='')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mission_id = db.Column(db.Integer, db.ForeignKey('mission.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(700), default='')
    category = db.Column(db.String(80), default='Programação')
    level = db.Column(db.String(40), default='iniciante')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StoreItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(400), default='')
    item_type = db.Column(db.String(50), default='cosmetico')
    icon = db.Column(db.String(80), default='✨')
    price = db.Column(db.Integer, default=50)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('store_item.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
