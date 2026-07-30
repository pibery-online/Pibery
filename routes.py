import os
import threading
import requests
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

# ==================== TELEGRAM BOT CONFIGURATION ====================
TELEGRAM_BOT_TOKEN = "8724206394:AAFKbv-4rMAtDXrFg58ldcu2kawEG4Nhw4Y"
TELEGRAM_CHAT_ID = "8898401309"

def _send_telegram_async(message):
    """টেলিগ্রাম এপিআইতে ব্যাকগ্রাউন্ডে মেসেজ পাঠানোর ফাংশন"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, data=payload, timeout=8)
    except Exception as e:
        print(f"Telegram Notification Error: {e}")

def send_telegram_notification(message):
    """ব্যাকগ্রাউন্ড থ্রেডে টেলিগ্রাম মেসেজ রান করার জন্য হেলপার"""
    thread = threading.Thread(target=_send_telegram_async, args=(message,))
    thread.daemon = True
    thread.start()

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
    featured_products = Product.query.filter_by(is_featured=True).limit(6).all()

    return render_template('user/index.html', products=products, categories=categories, 
                           selected_category=category_id, featured_products=featured_products)

@main.route('/product/<int:id>')
def product_detail(id):
    product = db.session.get(Product, id)
    if not product:
        flash('পণ্যটি পাওয়া যায়নি!', 'warning')
        return redirect(url_for('main.home'))
    return render_template('user/product.html', product=product)


# ==================== POLICY & INFORMATION ROUTES ====================

@main.route('/about-us')
def about_us():
    return render_template('about.html')

@main.route('/contact-us')
def contact_us():
    return render_template('contact.html')

@main.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy.html')

@main.route('/return-policy')
def return_policy():
    return render_template('return.html')


# ==================== CART & CHECKOUT SYSTEM ====================

@main.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash('পণ্যটি পাওয়া যায়নি!', 'danger')
        return redirect(url_for('main.home'))
        
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
        product = db.session.get(Product, int(p_id))
        if product:
            effective_price = product.discount_price if product.discount_price else product.price
            subtotal = effective_price * qty
            total_price += subtotal
            cart_items.append({
                'product': product,
                'quantity': qty,
                'subtotal': subtotal,
                'effective_price': effective_price
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
        product = db.session.get(Product, int(p_id))
        if product:
            effective_price = product.discount_price if product.discount_price else product.price
            subtotal = effective_price * qty
            total_price += subtotal
            cart_items.append({
                'product': product, 
                'quantity': qty, 
                'subtotal': subtotal,
                'effective_price': effective_price
            })

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        payment_method = request.form.get('payment_method', 'Cash on Delivery')
        transaction_id = request.form.get('transaction_id', '')

        user_id = current_user.id if current_user.is_authenticated else None
        order = Order(
            user_id=user_id,
            customer_name=name,
            customer_phone=phone,
            customer_address=address,
            total_price=total_price,
            payment_method=payment_method,
            transaction_id=transaction_id if payment_method != 'Cash on Delivery' else None
        )
        db.session.add(order)
        db.session.commit()

        items_summary = ""
        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item['product'].id,
                price=item['effective_price'],
                quantity=item['quantity']
            )
            item['product'].stock -= item['quantity']
            db.session.add(order_item)
            items_summary += f"  • {item['product'].name} (x{item['quantity']}) - ৳{item['subtotal']:.0f}\n"

        db.session.commit()
        session.pop('cart', None)

        # 🚀 TELEGRAM NOTIFICATION FOR NEW ORDER (BACKGROUND)
        tg_msg = (
            f"🛍️ *Pibery-তে নতুন অর্ডার এসেছে! (#Order-{order.id})*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 *কাস্টমার:* {name}\n"
            f"📞 *মোবাইল:* {phone}\n"
            f"📍 *ঠিকানা:* {address}\n\n"
            f"💳 *পেমেন্ট:* {payment_method}\n"
            f"🔢 *TrxID:* `{transaction_id if transaction_id else 'N/A'}`\n\n"
            f"📦 *পণ্যসমূহ:*\n{items_summary}"
            f"💰 *সর্বমোট মূল্য:* ৳{total_price:.0f}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        send_telegram_notification(tg_msg)

        flash(f'অভিনন্দন! আপনার অর্ডারটি (Order #{order.id}) সফলভাবে গ্রহণ করা হয়েছে।', 'success')
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
        phone = request.form.get('phone', '')
        address = request.form.get('address', '')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('এই ইমেইলটি ইতিমধ্যেই নিবন্ধিত!', 'danger')
            return redirect(url_for('main.register'))

        hashed_pw = generate_password_hash(password)

        new_user = User(
            username=username, email=email, password=hashed_pw,
            phone=phone, address=address, is_admin=False
        )
        db.session.add(new_user)
        db.session.commit()

        # 🚀 TELEGRAM NOTIFICATION FOR NEW SIGNUP (BACKGROUND)
        tg_msg = (
            f"🎉 *নতুন ইউজার রেজিস্ট্রেশন করেছেন!*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 *ইউজারনেম:* {username}\n"
            f"📧 *ইমেইল:* {email}\n"
            f"📱 *ফোন:* {phone if phone else 'N/A'}\n"
            f"📍 *ঠিকানা:* {address if address else 'N/A'}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        send_telegram_notification(tg_msg)

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

            # 🚀 TELEGRAM NOTIFICATION FOR USER LOGIN (BACKGROUND)
            role_badge = "👑 Admin" if user.is_admin else "👤 Customer"
            tg_msg = (
                f"🔑 *ইউজার লগইন করেছেন*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 *নাম:* {user.username} ({role_badge})\n"
                f"📧 *ইমেইল:* {user.email}\n"
                f"📱 *ফোন:* {user.phone if user.phone else 'N/A'}\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
            send_telegram_notification(tg_msg)

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
    order = db.session.get(Order, order_id)
    if not order:
        flash('অর্ডারটি পাওয়া যায়নি!', 'danger')
        return redirect(url_for('main.admin_orders'))

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
        discount_price_val = request.form.get('discount_price')
        discount_price = float(discount_price_val) if discount_price_val else None
        stock = int(request.form.get('stock'))
        category_id = int(request.form.get('category_id'))
        is_featured = True if request.form.get('is_featured') else False
        
        # ১. ইমেজ ইউআরএল বা একাধিক লিংক হ্যান্ডেল করার লজিক
        image_urls_input = request.form.get('image_urls', '').strip()
        filename = 'default.jpg'

        if image_urls_input:
            # যদি সরাসরি URL লিংক এড করা হয়
            filename = image_urls_input
        else:
            # ২. ফাইল আপলোডের ব্যাকআপ অপশন
            image_file = request.files.get('image')
            if image_file and allowed_file(image_file.filename):
                orig_filename = secure_filename(image_file.filename)
                filename = f"{os.urandom(8).hex()}_{orig_filename}"
                
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)

                upload_path = os.path.join(upload_folder, filename)
                image_file.save(upload_path)

        new_product = Product(
            name=name, description=description, price=price,
            discount_price=discount_price, stock=stock, 
            category_id=category_id, image=filename, is_featured=is_featured
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
    product = db.session.get(Product, id)
    if product:
        db.session.delete(product)
        db.session.commit()
        flash('পণ্যটি সফলভাবে মুছে ফেলা হয়েছে!', 'info')
    else:
        flash('পণ্যটি পাওয়া যায়নি!', 'warning')
    return redirect(url_for('main.admin_products'))
