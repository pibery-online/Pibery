from flask import Flask
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')

@app.route('/')
def home():
    return "<h1 style='color:green; text-align:center; margin-top:50px;'>🛍️ Welcome to Pibery E-commerce Server!</h1><p style='text-align:center;'>App is running successfully on Termux!</p>"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
