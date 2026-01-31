import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
import stripe
import logging

# ------------------ LOGGING ------------------
logging.basicConfig(level=logging.DEBUG)

# ------------------ CONFIG ------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ------------------ STRIPE ------------------
stripe.api_key = "sk_test_51S7FjoAEv95v9N8XFpcrO881hXXG5tFyh1W0uL9rOqBeos0R8nGJkw0kL0JOLU7ZHpazyfpbUIsBgBgpixPyqxIS006h4qtupf"
STRIPE_WEBHOOK_SECRET = "whsec_f9a2f5e61bce58c97982ca8ebd9760c7a2573782443da99cab8385957ff28736"

# ------------------ MODELS ------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    credits = db.Column(db.Integer, default=0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------ ROUTES ------------------

@app.route('/')
def home():
    return redirect(url_for('login'))

# ---------- SIGNUP ----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash("Usuario ya existe")
            return redirect(url_for('signup'))

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, password_hash=hashed)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('mvp'))

    return render_template('signup.html')

# ---------- LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('mvp'))

        flash("Usuario o contraseña incorrectos")

    return render_template('login.html')

# ---------- LOGOUT ----------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ---------- MVP / NORMALIZADOR ----------
@app.route('/mvp', methods=['GET', 'POST'])
@login_required
def mvp():
    if request.method == 'POST':
        files = request.files.getlist('files')
        if len(files) > current_user.credits:
            flash('No tienes suficientes créditos')
            return redirect(url_for('mvp'))

        # Aquí iría tu lógica de OCR + OpenAI
        for f in files:
            filename = secure_filename(f.filename)
            # f.save(os.path.join("uploads", filename))

        current_user.credits -= len(files)
        db.session.commit()
        flash(f'Procesados {len(files)} archivos. Créditos restantes: {current_user.credits}')

    return render_template('index.html', credits=current_user.credits)

# ---------- BUY CREDITS ----------
@app.route('/buy_credits')
@login_required
def buy_credits():
    # Configura price_id según tus productos en Stripe
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price': 'price_10credits_id',  # Reemplaza con tu price_id real
            'quantity': 1
        }],
        mode='payment',
        success_url=url_for('mvp', _external=True),
        cancel_url=url_for('mvp', _external=True),
        client_reference_id=current_user.id
    )
    return redirect(session.url)

# ---------- STRIPE WEBHOOK ----------
@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        app.logger.error(f"Webhook error: {e}")
        return jsonify(success=False), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['client_reference_id']
        user = User.query.get(user_id)

        # Ajusta la cantidad de créditos según el price_id real
        credits_to_add = 10
        user.credits += credits_to_add
        db.session.commit()

    return jsonify(success=True)

# ------------------ RUN ------------------
if __name__ == '__main__':
    db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
