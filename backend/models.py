from datetime import datetime
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


group_members = db.Table(
    'group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id', ondelete='CASCADE'), primary_key=True),
)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class User(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30), default='')
    bio = db.Column(db.String(500), default='')
    avatar = db.Column(db.Text, default='👨‍💻')
    xp = db.Column(db.Integer, default=0, nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    nodo_coins = db.Column(db.Integer, default=2, nullable=False)
    streak = db.Column(db.Integer, default=0, nullable=False)
    last_streak_date = db.Column(db.Date, nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_banned = db.Column(db.Boolean, default=False, nullable=False)
    token_version = db.Column(db.Integer, default=0, nullable=False)

    equipped_frame = db.Column(db.String(80), default='')
    equipped_banner = db.Column(db.String(80), default='')
    equipped_effect = db.Column(db.String(80), default='')
    equipped_badge = db.Column(db.String(80), default='')
    equipped_theme = db.Column(db.String(80), default='theme-obsidian')
    nameplate = db.Column(db.String(80), default='')


class Friend(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    addressee_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    status = db.Column(db.String(20), default='pending', nullable=False)
    __table_args__ = (
        db.CheckConstraint('requester_id <> addressee_id', name='friend_not_self'),
        db.UniqueConstraint('requester_id', 'addressee_id', name='unique_friend_direction'),
    )


class Group(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(400), default='')
    topic = db.Column(db.String(80), default='Programação')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    xp = db.Column(db.Integer, default=0, nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    members = db.relationship('User', secondary=group_members, backref='groups', lazy='select')


class Post(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(1000), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    user = db.relationship('User')


class PostLike(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', name='unique_post_like'),)


class PostComment(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    content = db.Column(db.String(700), nullable=False)
    user = db.relationship('User')


class ChatMessage(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    room = db.Column(db.String(120), default='global', nullable=False, index=True)
    content = db.Column(db.String(1000), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True)
    username = db.Column(db.String(120), default='Sistema')
    user = db.relationship('User')


class Mission(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(600), nullable=False)
    category = db.Column(db.String(80), default='Programação')
    difficulty = db.Column(db.String(30), default='iniciante')
    xp_reward = db.Column(db.Integer, default=30, nullable=False)
    coin_reward = db.Column(db.Integer, default=1, nullable=False)


class CompletedMission(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    answer = db.Column(db.String(1200), default='')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    mission_id = db.Column(db.Integer, db.ForeignKey('mission.id', ondelete='CASCADE'), nullable=False, index=True)
    __table_args__ = (db.UniqueConstraint('user_id', 'mission_id', name='unique_completed_mission'),)


class Course(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(700), default='')
    category = db.Column(db.String(80), default='Programação')
    level = db.Column(db.String(40), default='iniciante')


class StoreItem(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(400), default='')
    item_type = db.Column(db.String(50), default='badge')
    icon = db.Column(db.String(80), default='badge-founder', unique=True, nullable=False)
    rarity = db.Column(db.String(30), default='comum')
    price = db.Column(db.Integer, default=25, nullable=False)


class Purchase(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('store_item.id', ondelete='CASCADE'), nullable=False, index=True)
    __table_args__ = (db.UniqueConstraint('user_id', 'item_id', name='unique_purchase'),)


class Achievement(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(400), default='')
    icon = db.Column(db.String(80), default='achievement')
    xp_reward = db.Column(db.Integer, default=0, nullable=False)
    coin_reward = db.Column(db.Integer, default=0, nullable=False)


class UserAchievement(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id', ondelete='CASCADE'), nullable=False, index=True)
    achievement = db.relationship('Achievement')
    __table_args__ = (db.UniqueConstraint('user_id', 'achievement_id', name='unique_user_achievement'),)


class Notification(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(400), default='')
    kind = db.Column(db.String(50), default='info')
    action = db.Column(db.String(120), default='')
    is_read = db.Column(db.Boolean, default=False, nullable=False)


class Activity(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True)
    text = db.Column(db.String(260), nullable=False)
    kind = db.Column(db.String(50), default='activity')
    user = db.relationship('User')


class Report(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    target_type = db.Column(db.String(40), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(400), default='')
    status = db.Column(db.String(30), default='open', nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)


class AdminAudit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50), default='')
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    admin = db.relationship('User')
