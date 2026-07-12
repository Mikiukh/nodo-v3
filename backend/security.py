import datetime
import os
from functools import wraps

import bcrypt
import jwt
from flask import jsonify, request


ISSUER = 'nodo-api'
AUDIENCE = 'nodo-web'


def _jwt_secret():
    return os.getenv('JWT_SECRET', 'dev-secret-local-only')


def hash_password(password):
    return bcrypt.hashpw(str(password).encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')


def verify_password(password, hashed):
    try:
        return bcrypt.checkpw(str(password).encode('utf-8'), str(hashed).encode('utf-8'))
    except (ValueError, TypeError):
        return False


def make_token(user_id, token_version=0):
    now = datetime.datetime.now(datetime.timezone.utc)
    ttl_hours = max(1, min(int(os.getenv('JWT_TTL_HOURS', '168')), 720))
    payload = {
        'sub': str(int(user_id)),
        'ver': int(token_version or 0),
        'iat': now,
        'nbf': now,
        'exp': now + datetime.timedelta(hours=ttl_hours),
        'iss': ISSUER,
        'aud': AUDIENCE,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm='HS256')


def decode_token(token):
    return jwt.decode(
        token,
        _jwt_secret(),
        algorithms=['HS256'],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={'require': ['sub', 'ver', 'iat', 'exp', 'iss', 'aud']},
    )


def token_from_request():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return ''
    return auth.split(' ', 1)[1].strip()


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from models import User, db

        raw = token_from_request()
        if not raw:
            return jsonify({'error': 'Sessão ausente'}), 401
        try:
            payload = decode_token(raw)
            user_id = int(payload['sub'])
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Sessão expirada'}), 401
        except (jwt.InvalidTokenError, ValueError, TypeError):
            return jsonify({'error': 'Sessão inválida'}), 401

        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': 'Conta não encontrada'}), 401
        if user.is_banned:
            return jsonify({'error': 'Conta bloqueada'}), 403
        if int(payload.get('ver', -1)) != int(user.token_version or 0):
            return jsonify({'error': 'Sessão encerrada. Entre novamente.'}), 401

        request.user_id = user.id
        request.current_user = user
        request.token_payload = payload
        return fn(*args, **kwargs)

    return wrapper
