import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    _db_url = os.getenv('DATABASE_URL', 'sqlite:///chatbot.db')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_BASE_URL = os.getenv('APP_BASE_URL', '')
    ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '')

    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = 'gemini-3.1-flash-lite-preview'

    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRY_HOURS = int(os.getenv('JWT_EXPIRY_HOURS', '8'))

    SMTP_SERVER = os.getenv('SMTP_SERVER', '')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    ALERT_RECIPIENT_DEFAULT = os.getenv('ALERT_RECIPIENT_DEFAULT', '')
    ALERT_RECIPIENT_CRITIQUE = os.getenv('ALERT_RECIPIENT_CRITIQUE', '')
    ALERT_RECIPIENT_ELEVEE = os.getenv('ALERT_RECIPIENT_ELEVEE', '')
    ALERT_RECIPIENT_MODEREE = os.getenv('ALERT_RECIPIENT_MODEREE', '')

    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
    DATA_RETENTION_DAYS = int(os.getenv('DATA_RETENTION_DAYS', '365'))
    CSRF_SECRET = os.getenv('CSRF_SECRET', '')

    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'dev-encryption-key-change-me!!')

    MAX_MESSAGES_PER_HOUR = 60
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
