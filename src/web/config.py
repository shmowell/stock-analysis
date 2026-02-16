"""Flask configuration."""


class Config:
    SECRET_KEY = 'stock-analysis-local-dev'
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
