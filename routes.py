from flask import Blueprint, render_template, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

main = Blueprint('main', __name__)

# ১. হোমপেজ
@main.route('/')
def home():
    return render_template('user/index.html')

# ২. কাস্টমার রেজিস্ট্রেশন
@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        address = request.form.get('address')

        # ইমেইল চেক
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('এই ইমেইলটি ইতিমধ্যেই নিবন্ধিত! অন্য ইমেইল ব্যবহার করুন।', 'danger')
            return redirect(url_for('main.register'))

        # পাসওয়ার্ড হ্যাশ করা
        hashed_pw = generate_password_hash(password)
        
        # প্রথম ব্যবহারকারী স্বয়ংক্রিয়ভাবে এডমিন হবে
        is_admin_user = True if User.query.count() == 0 else False

        new_user = User(
            username=username,
            email=email,
            password=hashed_pw,
            phone=phone,
            address=address,
            is_admin=is_admin_user
        )
        db.session.add(new_user)
        db.session.commit()

        flash('আপনার রেজিস্ট্রেশন সফল হয়েছে! অনুগ্রহ করে লগইন করুন।', 'success')
        return redirect(url_for('main.login'))

    return render_template('user/register.html')

# ৩. কাস্টমার লগইন
@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'স্বাগতম {user.username}! সফলভাবে লগইন করেছেন।', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash('ভুল ইমেইল বা পাসওয়ার্ড! আবার চেষ্টা করুন।', 'danger')

    return render_template('user/login.html')

# ৪. লগআউট
@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('আপনি অ্যাকাউন্ট থেকে বের হয়ে গেছেন।', 'info')
    return redirect(url_for('main.home'))

# ৫. ইউজার প্রোফাইল
@main.route('/profile')
@login_required
def profile():
    return render_template('user/profile.html')
