import os, datetime, jwt, bcrypt
from functools import wraps
from flask import request, jsonify

def hash_password(password): return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
def verify_password(password, hashed): return bcrypt.checkpw(password.encode(), hashed.encode())
def make_token(user_id): return jwt.encode({'user_id': user_id, 'exp': datetime.datetime.utcnow()+datetime.timedelta(days=7)}, os.getenv('JWT_SECRET','dev-secret'), algorithm='HS256')
def decode_token(token): return jwt.decode(token, os.getenv('JWT_SECRET','dev-secret'), algorithms=['HS256'])
def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth=request.headers.get('Authorization','')
        if not auth.startswith('Bearer '): return jsonify({'error':'Token ausente'}),401
        try: request.user_id=decode_token(auth.split(' ',1)[1])['user_id']
        except Exception: return jsonify({'error':'Token inválido'}),401
        return fn(*args, **kwargs)
    return wrapper
