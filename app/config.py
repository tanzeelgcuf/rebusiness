"""
Flask Application Configuration
Multi-tenant SaaS platform settings
"""

import os
from datetime import timedelta


class Config:
    """Base configuration"""

    # Flask
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///rebusiness_automation_saas.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5000').split(',')

    # Redis (for Celery, caching)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'UTC'

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')

    # Multi-tenancy
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload

    # LLM Configuration
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini')  # gemini, openai, groq
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')

    # Company Info (defaults, can be overridden per tenant)
    RFQ_COMPANY_NAME = os.getenv('RFQ_COMPANY_NAME', 'CampSable LLC')
    RFQ_VENDOR_EMAIL = os.getenv('RFQ_VENDOR_EMAIL', 'bobbysmitty078@gmail.com')
    RFQ_COMPANY_CONTACT = os.getenv('RFQ_COMPANY_CONTACT', 'Bobby Smitty')
    RFQ_COMPANY_PHONE = os.getenv('RFQ_COMPANY_PHONE', '+1 (720) 980-6080')

    # SMTP Configuration (for email submission)
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    SMTP_SENDER_EMAIL = os.getenv('SMTP_SENDER_EMAIL', RFQ_VENDOR_EMAIL)

    # Proxy Configuration
    PROXY_ROTATION_ENABLED = os.getenv('PROXY_ROTATION_ENABLED', 'true').lower() == 'true'
    CAPSOLVER_API_KEY = os.getenv('CAPSOLVER_API_KEY')

    # Feature Flags
    FEATURE_THOMASNET_SUBMISSION = os.getenv('FEATURE_THOMASNET_SUBMISSION', 'true').lower() == 'true'
    FEATURE_EMAIL_SUBMISSION = os.getenv('FEATURE_EMAIL_SUBMISSION', 'true').lower() == 'true'
    FEATURE_BATCH_PROCESSING = os.getenv('FEATURE_BATCH_PROCESSING', 'true').lower() == 'true'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_ECHO = True


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    LOG_LEVEL = 'INFO'
    SQLALCHEMY_ECHO = False

    # Enforce secure settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


# Configuration by environment
CONFIG_BY_ENV = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}


def get_config(env=None):
    """Get configuration object by environment"""
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    return CONFIG_BY_ENV.get(env, DevelopmentConfig)
