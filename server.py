# server.py
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
# 🛑 SECURE KEYS (YAHAN APNI ASLI DETAILS DAALNA)
# ==========================================

MY_GMAIL = "support.automind@gmail.com"
MY_APP_PASS = "ovqg kjzf jovt hoab" # Apna 16-digit pass daalo

RAZORPAY_KEY_ID = "rzp_live_SYZHZG8szS0pmK"         # Apni asli Razorpay Key ID daalo
RAZORPAY_KEY_SECRET = "lFGX5TGJZQDKeB084BT8CQc6" # Apni asli Razorpay Secret daalo

# Firebase Config
config = {
    "apiKey": "AIzaSyBCAxW1E3vnZcf1L4rzbMT9BTeuWi342e8", # App.py se dekh kar apni API key daal dena
    "authDomain": "automind2004.firebaseapp.com",
    "databaseURL": "https://automind2004-default-rtdb.firebaseio.com",
    "projectId": "automind2004",
    "storageBucket": "automind2004.firebasestorage.app",
    "messagingSenderId": "665065376262",
    "appId": "1:665065376262:web:44644b195e9fc2a2311187"
}
firebase = pyrebase.initialize_app(config)
db = firebase.database()

rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ----------------- ROUTE 1: SEND OTP -----------------
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
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(MY_GMAIL, MY_APP_PASS)
        server.send_message(msg)
        server.quit()
        
        return jsonify({"status": "success", "otp": generated_otp}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ADMIN CREDENTIALS (Ab ye yahan safe rahenge) ---
ADMIN_ID = "starlord_X9#Core"      
ADMIN_PASS = "sharma1127app4104" # Apna asli admin password yahan likh dena

@app.route('/login-admin', methods=['POST'])
def login_admin():
    try:
        data = request.get_json()
        # Server check karega ki ID aur Pass match ho raha hai ya nahi
        if data.get('id') == ADMIN_ID and data.get('pass') == ADMIN_PASS:
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"status": "fail"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- AI SETTINGS ---
GEMINI_KEY = "AIzaSyAzIoEvbQ8ElvgL4_fxkkENKqQqrQKU2Ow" # Yahan apni asli Gemini key daalo
ai_client = genai.Client(api_key=GEMINI_KEY)

# ----------------- ROUTE 2: VERIFY PAYMENT -----------------
@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    try:
        data = request.get_json()
        pay_id = data.get('pay_id')
        user = data.get('user')
        credits_to_add = int(data.get('credits_to_add'))
        price = data.get('price')

        # 1. Razorpay se check karo payment hui ya nahi
        link_status = rzp_client.payment_link.fetch(pay_id)
        
        if link_status['status'] == 'paid':
            # 2. Check karo double payment toh nahi
            payment_log_ref = db.child("payment_logs").order_by_child("razorpay_link_id").equal_to(pay_id).get().val()
            if payment_log_ref:
                return jsonify({"status": "already_processed"}), 200

            # 3. Firebase mein Credits update karo
            user_ref = db.child("users").child(user).get().val()
            old_credits = int(user_ref.get('credits', 0))
            new_credits = old_credits + credits_to_add
            db.child("users").child(user).update({"credits": new_credits})
            
            # 4. Transaction Log Save karo
            secure_token = hash_password(f"{pay_id}_RazorPay_{credits_to_add}")
            db.child("payment_logs").push({
                "user": user, 
                "razorpay_link_id": pay_id, 
                "amount": price,
                "credits_added": credits_to_add,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Success",
                "verify_hash": secure_token
            })
            
            return jsonify({"status": "success", "new_credits": new_credits}), 200
        else:
            return jsonify({"status": "pending", "rzp_status": link_status['status']}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ----------------- ROUTE 3: GET AI ANSWER -----------------
@app.route('/get-ai-answer', methods=['POST'])
def get_ai_answer():
    try:
        data = request.get_json()
        question_text = data.get('question')
        
        # Prompt server par hi banega (Extra security)
        prompt = f"Write a short, natural human-like answer in English for: {question_text}. Keep it under 10 words."
        
        response = ai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        return jsonify({"status": "success", "answer": response.text.strip()}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

import os

if __name__ == '__main__':
    # Render khud batata hai ki kaunsa port use karna hai
    port = int(os.environ.get("PORT", 5000))
    print(f"AutoMind SECURE Server is Running on port {port}...")
    # 0.0.0.0 ka matlab hai ki server bahar ki duniya se connect ho sakta hai
    app.run(host='0.0.0.0', port=port)
