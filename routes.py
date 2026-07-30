import os
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Category, Product, Order, OrderItem

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

# সিক্রেট এডমিন প্রিফিক্স ইউআরএল
SECRET_ADMIN_PREFIX = '/pibery-secure-control-8831'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== CONTEXT PROCESSORS ====================
@main.context_processor
def inject_cart_count():
    cart = session.get('cart', {})
    cart_count = sum(cart.values()) if isinstance(cart, dict) else 0
    return dict(cart_count=cart_count)


# Admin Access Decorator (কঠোর সিকিউরিটি গার্ড)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('অনুমতি বিহীন প্রবেশ নিষিদ্ধ!', 'danger')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== USER ROUTES ====================

@main.route('/')
def home():
    category_id = request.args.get('category_id', type=int)
    search_query = request.args.get('search', '')

    categories = Category.query.all()
    query = Product.query

    if category_id:
        query = query.filter_by(category_id=category_id)
    if search_query:
        query = query.filter(Product.name.contains(search_query))

    products = query.order_by(Product.created_at.desc()).all()
    return render_template('user/index.html', products=products, categories=categories, selected_category=category_id)

@main.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    return render_template('user/product.html', product=product)


# ==================== CART & CHECKOUT SYSTEM ====================

@main.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']
    p_id = str(product_id)

    if p_id in cart:
        cart[p_id] += quantity
    else:
        cart[p_id] = quantity

    session.modified = True
    flash(f'"{product.name}" কার্টে যোগ করা হয়েছে!', 'success')
    return redirect(request.referrer or url_for('main.home'))

@main.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    cart_items = []
    total_price = 0.0

    for p_id, qty in cart.items():
        product = Product.query.get(int(p_id))
        if product:
            subtotal = product.price * qty
            total_price += subtotal
            cart_items.append({
                'product': product,
                'quantity': qty,
                'subtotal': subtotal
            })

    return render_template('user/cart.html', cart_items=cart_items, total_price=total_price)

@main.route('/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    p_id = str(product_id)

    if 'cart' in session and p_id in session['cart']:
        if quantity > 0:
            session['cart'][p_id] = quantity
        else:
            session['cart'].pop(p_id, None)
        session.modified = True
        flash('কার্ট আপডেট করা হয়েছে!', 'info')

    return redirect(url_for('main.view_cart'))

@main.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    p_id = str(product_id)
    if 'cart' in session and p_id in session['cart']:
        session['cart'].pop(p_id, None)
        session.modified = True
        flash('পণ্যটি কার্ট থেকে সরানো হয়েছে!', 'info')

    return redirect(url_for('main.view_cart'))

@main.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('আপনার কার্ট খালি! অর্ডার করতে পণ্য যোগ করুন।', 'warning')
        return redirect(url_for('main.home'))

    cart_items = []
    total_price = 0.0
    for p_id, qty in cart.items():
        product = Product.query.get(int(p_id))
        if product:
            subtotal = product.price * qty
            total_price += subtotal
            cart_items.append({'product': product, 'quantity': qty, 'subtotal': subtotal})

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')

        user_id = current_user.id if current_user.is_authenticated else None
        order = Order(
            user_id=user_id,
            customer_name=name,
            customer_phone=phone,
            customer_address=address,
            total_price=total_price,
            payment_method='Cash on Delivery'
        )
        db.session.add(order)
        db.session.commit()

        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item['product'].id,
                price=item['product'].price,
                quantity=item['quantity']
            )
            item['product'].stock -= item['quantity']
            db.session.add(order_item)

        db.session.commit()
        session.pop('cart', None)

        flash(f'অভিনন্দন! আপনার অর্ডারটি (Order #{order.id}) সফলভাবে নিশ্চিত করা হয়েছে।', 'success')
        return redirect(url_for('main.my_orders' if current_user.is_authenticated else 'main.home'))

    return render_template('user/checkout.html', cart_items=cart_items, total_price=total_price)

@main.route('/orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('user/orders.html', orders=orders)


# ==================== AUTH ROUTES ====================

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

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('এই ইমেইলটি ইতিমধ্যেই নিবন্ধিত!', 'danger')
            return redirect(url_for('main.register'))

        hashed_pw = generate_password_hash(password)

        # সিকিউরিটি রুল: ওয়েবসাইট থেকে যে কেউই রেজিস্টার করুক, সে সবসময় সাধারণ কাস্টমার (is_admin=False) হবে।
        new_user = User(
            username=username, email=email, password=hashed_pw,
            phone=phone, address=address, is_admin=False
        )
        db.session.add(new_user)
        db.session.commit()

        flash('রেজিস্ট্রেশন সফল হয়েছে! অনুগ্রহ করে লগইন করুন।', 'success')
        return redirect(url_for('main.login'))

    return render_template('user/register.html')

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
            flash(f'স্বাগতম {user.username}!', 'success')
            next_page = request.args.get('next')
            if user.is_admin:
                return redirect(url_for('main.admin_dashboard'))
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash('ভুল ইমেইল বা পাসওয়ার্ড!', 'danger')

    return render_template('user/login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('আপনি অ্যাকাউন্ট থেকে বের হয়ে গেছেন।', 'info')
    return redirect(url_for('main.home'))

@main.route('/profile')
@login_required
def profile():
    return render_template('user/profile.html')


# ==================== SECRET ADMIN ROUTES ====================

@main.route(f'{SECRET_ADMIN_PREFIX}/dashboard')
@login_required
@admin_required
def admin_dashboard():
    total_products = Product.query.count()
    total_categories = Category.query.count()
    total_users = User.query.count()
    total_orders = Order.query.count()

    delivered_orders = Order.query.filter_by(status='Delivered').all()
    total_sales = sum(order.total_price for order in delivered_orders)

    return render_template('admin/dashboard.html', 
                           total_products=total_products, 
                           total_categories=total_categories, 
                           total_users=total_users, 
                           total_orders=total_orders,
                           total_sales=total_sales)

@main.route(f'{SECRET_ADMIN_PREFIX}/orders')
@login_required
@admin_required
def admin_orders():
    status_filter = request.args.get('status', '')
    if status_filter:
        orders = Order.query.filter_by(status=status_filter).order_by(Order.created_at.desc()).all()
    else:
        orders = Order.query.order_by(Order.created_at.desc()).all()
        
    return render_template('admin/orders.html', orders=orders, current_status=status_filter)

@main.route(f'{SECRET_ADMIN_PREFIX}/order/update_status/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if new_status in ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']:
        order.status = new_status
        db.session.commit()
        flash(f'Order #{order.id} স্ট্যাটাস পরিবর্তন করে "{new_status}" করা হয়েছে!', 'success')
    
    return redirect(url_for('main.admin_orders'))

@main.route(f'{SECRET_ADMIN_PREFIX}/categories', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_categories():
    if request.method == 'POST':
        category_name = request.form.get('name')
        if category_name:
            existing = Category.query.filter_by(name=category_name).first()
            if not existing:
                new_cat = Category(name=category_name)
                db.session.add(new_cat)
                db.session.commit()
                flash('নতুন ক্যাটাগরি তৈরি সফল হয়েছে!', 'success')
            else:
                flash('এই ক্যাটাগরিটি আগেই তৈরি করা হয়েছে!', 'warning')
        return redirect(url_for('main.admin_categories'))

    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@main.route(f'{SECRET_ADMIN_PREFIX}/products', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_products():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        stock = int(request.form.get('stock'))
        category_id = int(request.form.get('category_id'))
        
        image_file = request.files.get('image')
        filename = 'default.jpg'

        if image_file and allowed_file(image_file.filename):
            orig_filename = secure_filename(image_file.filename)
            filename = f"{os.urandom(8).hex()}_{orig_filename}"
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            image_file.save(upload_path)

        new_product = Product(
            name=name, description=description, price=price,
            stock=stock, category_id=category_id, image=filename
        )
        db.session.add(new_product)
        db.session.commit()
        flash('নতুন পণ্য সফলভাবে যোগ করা হয়েছে!', 'success')
        return redirect(url_for('main.admin_products'))

    products = Product.query.order_by(Product.created_at.desc()).all()
    categories = Category.query.all()
    return render_template('admin/products.html', products=products, categories=categories)

@main.route(f'{SECRET_ADMIN_PREFIX}/product/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('পণ্যটি সফলভাবে মুছে ফেলা হয়েছে!', 'info')
    return redirect(url_for('main.admin_products'))
