import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import stripe

app = Flask(__name__)

# Secret key para sesiones
app.secret_key = os.environ.get('SECRET_KEY', 'cualquier_cosa_segura')

# Configuración de la base de datos
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# --------------------
# MODELOS
# --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    credits = db.Column(db.Integer, default=0)

# Crear tablas en contexto de la app
with app.app_context():
    db.create_all()

# --------------------
# RUTAS LOGIN / SIGNUP
# --------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('mvp'))
        else:
            flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Usuario ya existe')
            return redirect(url_for('signup'))
        hashed_pw = generate_password_hash(password, method='sha256')
        user = User(username=username, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('mvp'))
    return render_template('signup.html')

# --------------------
# RUTA DEL MVP
# --------------------
@app.route('/mvp', methods=['GET', 'POST'])
def mvp():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('index.html', credits=user.credits)

# --------------------
# COMPRAR CREDITOS (Stripe Checkout)
# --------------------
@app.route('/buy_credits/<int:amount>')
def buy_credits(amount):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    session_user = User.query.get(session['user_id'])
    
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {'name': f'{amount} Credits'},
                'unit_amount': amount * 100,  # $1 = 1 crédito
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=url_for('checkout_success', _external=True) + f'?user_id={session_user.id}&credits={amount}',
        cancel_url=url_for('mvp', _external=True),
    )
    return redirect(checkout_session.url)

@app.route('/checkout_success')
def checkout_success():
    user_id = request.args.get('user_id')
    credits = int(request.args.get('credits', 0))
    user = User.query.get(user_id)
    if user:
        user.credits += credits
        db.session.commit()
    flash(f'Compra completada: {credits} créditos agregados')
    return redirect(url_for('mvp'))

# --------------------
# CERRAR SESIÓN
# --------------------
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# --------------------
# RUN
# --------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
