"""Authentication utilities: JWT, bcrypt, decorators."""
from functools import wraps
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError
from flask import g, jsonify, redirect, url_for, request
from config import Config


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (cost factor 12)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def generate_token(user_id: str, role: str) -> str:
    """Generate a JWT token."""
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=Config.JWT_EXPIRY_HOURS),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm=Config.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def login_required(f):
    """Decorator: require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'current_user') or g.current_user is None:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentification requise'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Decorator: require specific role(s)."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user') or g.current_user is None:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentification requise'}), 401
                return redirect(url_for('login_page'))
            if g.current_user.role not in roles:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Permissions insuffisantes'}), 403
                return redirect(url_for('login_page'))
            return f(*args, **kwargs)
        return decorated
    return decorator
