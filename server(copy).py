from flask import Flask, request, jsonify
import time, hmac, hashlib

app = Flask(__name__)

# In-memory token store for demo. Use persistent DB in production.
TOKENS = {}  # token -> {'user_id': str, 'expires': timestamp, 'used': False}

# Example route for bot to create token (in production this is called by your bot)
@app.route('/create_token', methods=['POST'])
def create_token():
    data = request.json
    user_id = str(data['user_id'])
    token = hashlib.sha256(f"{user_id}-{time.time()}".encode()).hexdigest()[:32]
    TOKENS[token] = {'user_id': user_id, 'expires': time.time() + 300, 'used': False}  # 5 min
    return jsonify({'token': token})

# Callback endpoint that ad page calls when ad is completed
@app.route('/ad_callback', methods=['POST'])
def ad_callback():
    data = request.json or {}
    token = data.get('token')
    user_id = str(data.get('user_id'))
    if not token or token not in TOKENS:
        return jsonify({'status': 'error', 'message': 'Invalid token'}), 400

    rec = TOKENS[token]
    if rec['used']:
        return jsonify({'status': 'error', 'message': 'Token already used'}), 400
    if rec['user_id'] != user_id:
        return jsonify({'status': 'error', 'message': 'User mismatch'}), 400
    if time.time() > rec['expires']:
        return jsonify({'status': 'error', 'message': 'Token expired'}), 400

    # OK: mark used and credit user
    rec['used'] = True
    # TODO: credit the user in your DB (e.g., add coins/credit)
    print(f"Credit user {user_id} for ad watch (token {token})")

    # Optionally, notify Telegram bot to send confirmation message:
    # call your bot function or publish to a queue
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)