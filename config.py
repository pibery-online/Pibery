import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # App Security & DB setup
    SECRET_KEY = os.getenv('SECRET_KEY', 'pibery_super_secret_key_2026')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///pibery.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Image Upload Setup (16MB max upload size)
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
