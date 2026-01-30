import os
from flask import Flask, request, render_template, send_file, jsonify
from utils import process_documents
import stripe
from config import STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY

app = Flask(__name__)

# ---------- Stripe setup ----------
stripe.api_key = STRIPE_SECRET_KEY

# Simple in-memory "users" dict for MVP
# user_id -> credits
USERS = {
    "demo_user": 5  # ejemplo inicial: 5 créditos
}

# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("index.html", stripe_key=STRIPE_PUBLISHABLE_KEY)

@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    data = request.json
    user_id = data.get("user_id")
    credits_to_buy = data.get("credits", 1)

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": f"{credits_to_buy} Invoice Credits"},
                "unit_amount": 100 * credits_to_buy,  # $1 por crédito
            },
            "quantity": 1,
        }],
        success_url=f"{data.get('success_url')}?session_id={{CHECKOUT_SESSION_ID}}&user_id={user_id}",
        cancel_url=f"{data.get('cancel_url')}",
    )
    return jsonify({"id": session.id})

@app.route("/upload", methods=["POST"])
def upload_file():
    user_id = request.form.get("user_id", "demo_user")

    if USERS.get(user_id, 0) <= 0:
        return jsonify({"error": "Not enough credits"}), 403

    uploaded_files = request.files.getlist("files")
    filepaths = []

    for file in uploaded_files:
        path = os.path.join("uploads", file.filename)
        os.makedirs("uploads", exist_ok=True)
        file.save(path)
        filepaths.append(path)

    output_path = process_documents(filepaths)

    # Deduct 1 credit per uploaded file
    USERS[user_id] -= len(uploaded_files)

    return send_file(output_path, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
