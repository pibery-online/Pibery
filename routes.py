from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from extensions import db
from models import User, Product, Category, CartItem, Order, OrderItem, Wishlist

main = Blueprint('main', __name__)

@main.route('/')
def home():
    category_id = request.args.get('category_id', type=int)
    search_query = request.args.get('search', '')

    query = Product.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))

    products = query.all()
    categories = Category.query.all()
    featured_products = Product.query.filter_by(is_featured=True).all()

    cart_count = 0
    if current_user.is_authenticated:
        cart_count = db.session.query(db.func.sum(CartItem.quantity)).filter_by(user_id=current_user.id).scalar() or 0

    return render_template('user/index.html', products=products, categories=categories, 
                           featured_products=featured_products, selected_category=category_id, cart_count=cart_count)

@main.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    cart_count = 0
    if current_user.is_authenticated:
        cart_count = db.session.query(db.func.sum(CartItem.quantity)).filter_by(user_id=current_user.id).scalar() or 0
    return render_template('user/product.html', product=product, cart_count=cart_count)

@main.route('/cart')
@login_required
def view_cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total_price = sum(item.product.discount_price * item.quantity if item.product.discount_price else item.product.price * item.quantity for item in cart_items)
    return render_template('user/cart.html', cart_items=cart_items, total_price=total_price)

@main.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    product = Product.query.get_or_404(product_id)
    
    if product.stock < quantity:
        flash('পর্যাপ্ত স্টক নেই!', 'danger')
        return redirect(request.referrer or url_for('main.home'))

    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)
    
    db.session.commit()
    flash('পণ্যটি কার্টে যোগ করা হয়েছে!', 'success')
    return redirect(request.referrer or url_for('main.home'))

@main.route('/cart/remove/<int:product_id>')
@login_required
def remove_from_cart(product_id):
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
        flash('কার্ট থেকে পণ্য মুছে ফেলা হয়েছে।', 'success')
    return redirect(url_for('main.view_cart'))

@main.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('আপনার কার্ট খালি!', 'warning')
        return redirect(url_for('main.home'))

    total_price = sum(item.product.discount_price * item.quantity if item.product.discount_price else item.product.price * item.quantity for item in cart_items)

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        payment_method = request.form.get('payment_method')
        transaction_id = request.form.get('transaction_id')

        order = Order(
            user_id=current_user.id,
            customer_name=name,
            customer_phone=phone,
            customer_address=address,
            payment_method=payment_method,
            transaction_id=transaction_id,
            total_price=total_price,
            status='Pending'
        )
        db.session.add(order)
        db.session.commit()

        for item in cart_items:
            price = item.product.discount_price if item.product.discount_price else item.product.price
            order_item = OrderItem(order_id=order.id, product_id=item.product.id, quantity=item.quantity, price=price)
            db.session.add(order_item)
            item.product.stock -= item.quantity
            db.session.delete(item)

        db.session.commit()
        flash(f'আপনার অর্ডার সফলভাবে সম্পন্ন হয়েছে!', 'success')
        return redirect(url_for('main.user_orders'))

    return render_template('user/checkout.html', cart_items=cart_items, total_price=total_price)

@main.route('/orders')
@login_required
def user_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('user/orders.html', orders=orders)

@main.route('/track-order', methods=['GET', 'POST'])
def track_order():
    order = None
    order_id = request.args.get('order_id')
    if order_id:
        order = Order.query.filter_by(id=order_id).first()
        if not order:
            flash('এই আইডি দিয়ে কোনো অর্ডার খুঁজে পাওয়া যায়নি!', 'danger')
    return render_template('track_order.html', order=order, order_id=order_id)

@main.route('/wishlist')
@login_required
def view_wishlist():
    wishlist_items = Wishlist.query.filter_by(user_id=current_user.id).all()
    return render_template('wishlist.html', wishlist_items=wishlist_items)

@main.route('/profile')
@login_required
def profile():
    return render_template('user/profile.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('রেজিস্ট্রেশন সফল!', 'success')
        return redirect(url_for('main.login'))
    return render_template('user/register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main.home'))
        flash('ভুল ইমেইল বা পাসওয়ার্ড', 'danger')
    return render_template('user/login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('লগআউট করা হয়েছে।', 'info')
    return redirect(url_for('main.home'))

# --- Admin Routes ---
@main.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('আপনার এই পেজে ঢোকার অনুমতি নেই!', 'danger')
        return redirect(url_for('main.home'))
    return render_template('admin/dashboard.html')

@main.route('/admin/products')
@login_required
def admin_products():
    if not current_user.is_admin:
        return redirect(url_for('main.home'))
    products = Product.query.all()
    return render_template('admin/products.html', products=products)

@main.route('/admin/categories', methods=['GET', 'POST'])
@login_required
def admin_categories():
    if not current_user.is_admin:
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            new_category = Category(name=name)
            db.session.add(new_category)
            db.session.commit()
            flash('নতুন ক্যাটাগরি সফলভাবে যোগ করা হয়েছে!', 'success')
            return redirect(url_for('main.admin_categories'))

    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@main.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        return redirect(url_for('main.home'))
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)
