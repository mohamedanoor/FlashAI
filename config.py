import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

    database_url = os.environ.get('DATABASE_URL', 'sqlite:///flashcards.db')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg'}

    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    DEFAULT_MODEL = 'claude-sonnet-4-5'
    MAX_TOKENS = 2000

    RATELIMIT_STORAGE_URL = "memory://"
    RATELIMIT_DEFAULT = "100 per hour"
    RATELIMIT_HEADERS_ENABLED = True

    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300

    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    MODEL_COSTS = {
        'claude-opus-4-5':   0.015,
        'claude-sonnet-4-5': 0.003,
        'claude-haiku-4-5':  0.00025,
    }