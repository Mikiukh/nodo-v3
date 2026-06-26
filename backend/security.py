import os
import datetime
import jwt
import bcrypt
from functools import wraps
from flask import request, jsonify


def _jwt_secret():
    return os.getenv('JWT_SECRET', 'dev-secret-local-only')


def hash_password(password):
    return bcrypt.hashpw(str(password).encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')


def verify_password(password, hashed):
    try:
        return bcrypt.checkpw(str(password).encode('utf-8'), str(hashed).encode('utf-8'))
    except Exception:
        return False


def make_token(user_id):
    now = datetime.datetime.utcnow()
    payload = {
        'user_id': int(user_id),
        'iat': now,
        'exp': now + datetime.timedelta(days=7),
        'iss': 'nodo-api',
    }
    return jwt.encode(payload, _jwt_secret(), algorithm='HS256')


def decode_token(token):
    return jwt.decode(token, _jwt_secret(), algorithms=['HS256'], issuer='nodo-api')


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Token ausente'}), 401
        try:
            request.user_id = decode_token(auth.split(' ', 1)[1])['user_id']
        except Exception:
            return jsonify({'error': 'Token inválido'}), 401
        return fn(*args, **kwargs)
    return wrapper
