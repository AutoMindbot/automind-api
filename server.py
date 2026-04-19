import os
from flask import Flask, request, jsonify
import smtplib
import random
from email.message import EmailMessage
import pyrebase
import razorpay
from datetime import datetime
import hashlib
from google import genai

app = Flask(__name__)

# ==========================================
# 🛑 SECURE KEYS FROM RENDER ENVIRONMENT
# ==========================================

MY_GMAIL = "support.automind@gmail.com"
MY_APP_PASS = os.environ.get("MY_APP_PASS")
ADMIN_ID = os.environ.get('ADMIN_ID')      
ADMIN_PASS = os.environ.get('ADMIN_PASS')

# Firebase Config
config = {
    "apiKey": os.environ.get("FIREBASE_API_KEY"),
    "authDomain": "automind2004.firebaseapp.com",
    "databaseURL": "https://automind2004-default-rtdb.firebaseio.com",
    "projectId": "automind2004",
    "storageBucket": "automind2004.firebasestorage.app",
    "messagingSenderId": "665065376262",
    "appId": "1:665065376262:web:44644b195e9fc2a2311187"
}
firebase = pyrebase.initialize_app(config)
db = firebase.database()

# Unified Razorpay Client
razor_client = razorpay.Client(auth=(
    os.environ.get("RAZORPAY_KEY_ID"), 
    os.environ.get("RAZORPAY_KEY_SECRET")
))

# AI Client
ai_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ----------------- ROUTES -----------------

@app.route('/send-otp', methods=['POST'])
def send_otp():
    try:
        data = request.get_json()
        target_email = data.get('email')
        if not target_email: return jsonify({"status": "error", "message": "Email required"}), 400
        generated_otp = str(random.randint(100000, 999999))
        msg = EmailMessage()
        msg.set_content(f"AutoMindBOT Code: {generated_otp}")
        msg['Subject'] = "AutoMindBOT Secure Verification"
        msg['From'] = MY_GMAIL
        msg['To'] = target_email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(MY_GMAIL, MY_APP_PASS)
            server.send_message(msg)
        return jsonify({"status": "success", "otp": generated_otp}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/login-admin', methods=['POST'])
def login_admin():
    try:
        data = request.get_json()
        if data.get('id') == ADMIN_ID and data.get('pass') == ADMIN_PASS:
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "fail"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/create-payment', methods=['POST'])
def create_payment():
    try:
        data = request.json
        amount = int(float(data.get("price")) * 100)
        payment_link = razor_client.payment_link.create({
            "amount": amount,
            "currency": "INR",
            "description": f"AutoMind - {data.get('credits')} Credits",
            "customer": {"name": data.get("username"), "email": data.get("email", "user@example.com")},
            "notify": {"sms": False, "email": False}
        })
        return jsonify({"status": "success", "pay_url": payment_link['short_url'], "pay_id": payment_link['id']})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    try:
        data = request.get_json()
        pay_id = data.get('pay_id')
        user = data.get('user')
        credits_to_add = data.get('credits_to_add')
        price = data.get('price')

        link_status = razor_client.payment_link.fetch(pay_id)
        
        if link_status['status'] == 'paid':
            # 1. Duplicate check
            logs = db.child("payment_logs").order_by_child("razorpay_link_id").equal_to(pay_id).get().val()
            if logs: return jsonify({"status": "already_processed"}), 200

            # 2. Credits update (Strict Integer conversion)
            if user and credits_to_add:
                user_ref = db.child("users").child(user).get().val()
                if user_ref:
                    new_credits = int(user_ref.get('credits', 0)) + int(credits_to_add)
                    db.child("users").child(user).update({"credits": new_credits})
                    
                    # 3. Secure Log entry
                    secure_token = hash_password(f"{pay_id}_RazorPay_{credits_to_add}")
                    db.child("payment_logs").push({
                        "user": user, "razorpay_link_id": pay_id, 
                        "amount": price, "credits_added": credits_to_add,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "Success", "verify_hash": secure_token
                    })
                    return jsonify({"status": "paid", "new_credits": new_credits}), 200
            return jsonify({"status": "paid"}), 200
        return jsonify({"status": "pending"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get-ai-answer', methods=['POST'])
def get_ai_answer():
    try:
        data = request.get_json()
        prompt = f"Write a short, natural human-like answer in English for: {data.get('question')}. Keep it under 10 words."
        response = ai_client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        return jsonify({"status": "success", "answer": response.text.strip()}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
