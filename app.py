from flask import Flask
from config import Config
from models import db, User
from flask_login import LoginManager

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
    return User.query.get(int(user_id))

# Register Blueprints
from routes import main
app.register_blueprint(main)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
