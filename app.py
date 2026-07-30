from flask import Flask
from config import Config
from models import db

app = Flask(__name__)
app.config.from_object(Config)

# Database connect
db.init_app(app)

# Table creation inside app context
with app.app_context():
    db.create_all()
    print("✅ Pibery Database & Tables Created Successfully!")

@app.route('/')
def home():
    return """
    <div style='text-align:center; padding:50px; font-family:sans-serif;'>
        <h1 style='color:#0d6efd;'>🛍️ Welcome to Pibery Server!</h1>
        <p style='color:#198754; font-weight:bold;'>SQLite Database & Models initialized successfully.</p>
    </div>
    """

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
