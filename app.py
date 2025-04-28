from flask import Flask, redirect, url_for
from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.student import student_bp
from routes.staff import staff_bp
from routes.sit_in import sit_in_bp
from db import init_db
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Configure session to be more secure
app.config.update(
    SECRET_KEY=os.urandom(24),  # Generate a random secret key
    SESSION_COOKIE_SECURE=True,  # Only send cookie over HTTPS
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE='Lax',  # Protect against CSRF
    PERMANENT_SESSION_LIFETIME=1800,  # 30 minutes session lifetime
    SESSION_REFRESH_EACH_REQUEST=True,  # Refresh session on each request
    SESSION_COOKIE_NAME='sit_in_session'  # Custom session cookie name
)

# Register blueprints without prefixes
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(student_bp)
app.register_blueprint(staff_bp)
app.register_blueprint(sit_in_bp)

# Initialize database
init_db()

@app.route('/')
def index():
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True) 