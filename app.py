from flask import Flask
from config import Config
from extensions import db
from models import User
from flask_login import LoginManager
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config.from_object(Config)

# Database Connect
db.init_app(app)

# Flask-Login Setup
login_manager = LoginManager()
login_manager.login_view = 'main.login'
login_manager.login_message = 'এই পেজে ঢুকতে আগে লগইন করুন।'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Register Blueprints
from routes import main
app.register_blueprint(main)

# অটোমেটিক এডমিন ইউজার তৈরি/আপডেট করার ফাংশন
def init_admin():
    email = "info.pibery@gmail.com"
    password = "Pibery.1280.Ahmed#COM"
    
    user = User.query.filter_by(email=email).first()
    if not user:
        new_admin = User(
            username="Pibery Admin",
            email=email,
            password=generate_password_hash(password),
            is_admin=True
        )
        db.session.add(new_admin)
        db.session.commit()
        print("🎉 Admin account created successfully!")
    else:
        user.password = generate_password_hash(password)
        user.is_admin = True
        db.session.commit()
        print("✅ Admin account updated successfully!")

# ডাটাবেজ টেবিল রিফ্রেশ এবং এডমিন তৈরি
with app.app_context():
    try:
        db.create_all()
        init_admin()
    except Exception as e:
        print("Database initialization note:", e)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
