from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

from models import db, User, Product, Category, CartItem, Order, OrderItem, Wishlist

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

    return render_template('index.html', products=products, categories=categories, 
                           featured_products=featured_products, selected_category=category_id, cart_count=cart_count)

@main.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    cart_count = 0
    if current_user.is_authenticated:
        cart_count = db.session.query(db.func.sum(CartItem.quantity)).filter_by(user_id=current_user.id).scalar() or 0
    return render_template('product.html', product=product, cart_count=cart_count)

@main.route('/cart')
@login_required
def view_cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total_price = sum(item.product.discount_price * item.quantity if item.product.discount_price else item.product.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

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
            
            # Stock reduce
            item.product.stock -= item.quantity
            db.session.delete(item)

        db.session.commit()
        flash(f'আপনার অর্ডার সফলভাবে সম্পন্ন হয়েছে! অর্ডার আইডি: #{order.id}', 'success')
        return redirect(url_for('main.user_orders'))

    return render_template('checkout.html', cart_items=cart_items, total_price=total_price)

@main.route('/orders')
@login_required
def user_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=orders)

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

@main.route('/wishlist/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_wishlist(product_id):
    existing = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if not existing:
        item = Wishlist(user_id=current_user.id, product_id=product_id)
        db.session.add(item)
        db.session.commit()
        flash('পণ্যটি উইশলিস্টে যুক্ত হয়েছে!', 'success')
    else:
        flash('পণ্যটি ইতিমধ্যে উইশলিস্টে আছে।', 'info')
    return redirect(request.referrer or url_for('main.home'))

@main.route('/wishlist/remove/<int:id>', methods=['POST'])
@login_required
def remove_from_wishlist(id):
    item = Wishlist.query.get_or_404(id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('উইশলিস্ট থেকে সরানো হয়েছে।', 'success')
    return redirect(url_for('main.view_wishlist'))

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('এই ইমেইল দিয়ে ইতিপূর্বে অ্যাকাউন্ট খোলা হয়েছে!', 'danger')
            return redirect(url_for('main.register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, phone=phone, address=address, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('সফলভাবে রেজিস্ট্রেশন সম্পন্ন হয়েছে! এখন লগইন করুন।', 'success')
        return redirect(url_for('main.login'))

    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('সফলভাবে লগইন করেছেন!', 'success')
            return redirect(url_for('main.admin_dashboard' if user.is_admin else 'main.home'))
        else:
            flash('ইমেইল অথবা পাসওয়ার্ড ভুল হয়েছে!', 'danger')

    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('লগআউট করা হয়েছে।', 'info')
    return redirect(url_for('main.home'))

@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

# --- Admin Routes ---
@main.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('আপনার এই পেজে প্রবেশের অনুমতি নেই!', 'danger')
        return redirect(url_for('main.home'))
    
    total_products = Product.query.count()
    total_categories = Category.query.count()
    total_orders = Order.query.count()
    total_users = User.query.count()
    return render_template('dashboard.html', total_products=total_products, total_categories=total_categories, total_orders=total_orders, total_users=total_users)

@main.route('/admin/products', methods=['GET', 'POST'])
@login_required
def admin_products():
    if not current_user.is_admin:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price'))
        discount_price = request.form.get('discount_price')
        discount_price = float(discount_price) if discount_price else None
        stock = int(request.form.get('stock'))
        category_id = int(request.form.get('category_id'))
        is_featured = True if request.form.get('is_featured') else False
        description = request.form.get('description')
        image_urls = request.form.get('image_urls')

        image_filename = 'default.jpg'
        if image_urls:
            image_filename = image_urls.strip()
        elif 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                upload_folder = os.path.join('static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                image_filename = filename

        product = Product(name=name, price=price, discount_price=discount_price, stock=stock, 
                          category_id=category_id, is_featured=is_featured, description=description, image=image_filename)
        db.session.add(product)
        db.session.commit()
        flash('পণ্য সফলভাবে যোগ করা হয়েছে!', 'success')
        return redirect(url_for('main.admin_products'))

    products = Product.query.all()
    categories = Category.query.all()
    return render_template('admin_products.html', products=products, categories=categories)

@main.route('/admin/product/delete/<int:id>', methods=['POST'])
@login_required
def delete_product(id):
    if not current_user.is_admin:
        return redirect(url_for('main.home'))
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('পণ্যটি মুছে ফেলা হয়েছে।', 'success')
    return redirect(url_for('main.admin_products'))

@main.route('/admin/categories', methods=['GET', 'POST'])
@login_required
def admin_categories():
    if not current_user.is_admin:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            category = Category(name=name)
            db.session.add(category)
            db.session.commit()
            flash('ক্যাটাগরি যোগ করা হয়েছে!', 'success')
        return redirect(url_for('main.admin_categories'))

    categories = Category.query.all()
    return render_template('categories.html', categories=categories)

@main.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        return redirect(url_for('main.home'))
    
    status = request.args.get('status')
    if status:
        orders = Order.query.filter_by(status=status).order_by(Order.created_at.desc()).all()
    else:
        orders = Order.query.order_by(Order.created_at.desc()).all()
        
    return render_template('admin_orders.html', orders=orders, current_status=status)

@main.route('/admin/order/update/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    if not current_user.is_admin:
        return redirect(url_for('main.home'))
    
    order = Order.query.get_or_404(order_id)
    status = request.form.get('status')
    if status:
        order.status = status
        db.session.commit()
        flash(f'অর্ডার #{order.id} স্ট্যাটাস পরিবর্তন করে "{status}" করা হয়েছে।', 'success')
        
    return redirect(url_for('main.admin_orders'))
