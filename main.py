import os
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import stripe

# --- Configuración Flask ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')  # ahora obligatorio
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Inicializar DB ---
db = SQLAlchemy(app)

# --- Login Manager ---
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# --- Stripe ---
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')

# --- Modelos ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    credits = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# --- Cargar usuario ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('mvp'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('mvp'))
        else:
            flash("Usuario o contraseña incorrectos")
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash("Usuario ya existe")
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('mvp'))
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- MVP Route ---
@app.route('/mvp')
@login_required
def mvp():
    return render_template('index.html', credits=current_user.credits, stripe_publishable_key=STRIPE_PUBLISHABLE_KEY)

# --- Comprar créditos ---
@app.route('/buy_credits', methods=['POST'])
@login_required
def buy_credits():
    pack = int(request.form.get('pack'))  # 10,50,100,...
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': f'{pack} credits'},
                    'unit_amount': pack * 100,  # 1 crédito = $1
                },
                'quantity': 1,
            }],
            success_url=url_for('success', _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for('mvp', _external=True),
        )
        return redirect(session.url, code=303)
    except Exception as e:
        return str(e)

@app.route('/success')
@login_required
def success():
    # Aquí podrías verificar la sesión de Stripe y añadir créditos automáticamente
    flash("Pago realizado correctamente. Créditos añadidos manualmente por ahora.")
    return redirect(url_for('mvp'))

# --- Inicializar DB dentro de app context ---
with app.app_context():
    db.create_all()

# --- Run ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
