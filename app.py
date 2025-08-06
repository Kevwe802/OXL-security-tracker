from flask import Flask, send_from_directory, request, jsonify, render_template, redirect, url_for, flash
from flask_socketio import SocketIO, join_room, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
from flask_cors import CORS
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'oxl-location-app'  # Change this to a secure random key in production
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = 'login'
online_users = defaultdict(lambda: False)

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) if user_id in ['admin'] else None  # Simple in-memory user

def init_db():
    conn = sqlite3.connect('locations.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS locations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT, latitude REAL, longitude REAL, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS location_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT, latitude REAL, longitude REAL, timestamp TEXT)''')
    conn.commit()
    conn.close()

@app.route('/')
def serve_sender():
    return send_from_directory('static', 'location_sender.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'oxlocation':  # Change to secure password in production
            user = User('admin')
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('serve_dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def serve_dashboard():
    return send_from_directory('static', 'dashboard.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/store_location', methods=['POST'])
def store_location():
    try:
        data = request.get_json()
        user_id = data['user_id']
        latitude = data['latitude']
        longitude = data['longitude']
        timestamp = data['timestamp']

        conn = sqlite3.connect('locations.db')
        c = conn.cursor()
        c.execute("INSERT INTO locations (user_id, latitude, longitude, timestamp) VALUES (?, ?, ?, ?)",
                  (user_id, latitude, longitude, timestamp))
        c.execute("INSERT INTO location_history (user_id, latitude, longitude, timestamp) VALUES (?, ?, ?, ?)",
                  (user_id, latitude, longitude, timestamp))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Location stored'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_users', methods=['GET'])
def get_users():
    try:
        conn = sqlite3.connect('locations.db')
        c = conn.cursor()
        c.execute("SELECT DISTINCT user_id FROM locations")
        user_ids = [row[0] for row in c.fetchall()]
        users = []
        for user_id in user_ids:
            c.execute("SELECT latitude, longitude, timestamp FROM locations WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
            current_location = c.fetchone()
            c.execute("SELECT latitude, longitude, timestamp FROM location_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10", (user_id,))
            history = c.fetchall()
            users.append({
                'user_id': user_id,
                'latitude': current_location[0] if current_location else None,
                'longitude': current_location[1] if current_location else None,
                'timestamp': current_location[2] if current_location else None,
                'history': [{'latitude': lat, 'longitude': lon, 'timestamp': ts} for lat, lon, ts in history]
            })
        conn.close()
        return jsonify({'status': 'success', 'users': users})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@socketio.on('join')
def on_join(data):
    user_id = data['user_id']
    join_room(user_id)
    online_users[user_id] = True
    emit('user_status', {'user_id': user_id, 'online': True}, broadcast=True)

@socketio.on('leave')
def on_leave(data):
    user_id = data['user_id']
    online_users[user_id] = False
    emit('user_status', {'user_id': user_id, 'online': False}, broadcast=True)

@socketio.on('location_update')
def on_location_update(data):
    user_id = data['user_id']
    latitude = data['latitude']
    longitude = data['longitude']
    timestamp = datetime.utcnow().isoformat()
    conn = sqlite3.connect('locations.db')
    c = conn.cursor()
    c.execute("INSERT INTO locations (user_id, latitude, longitude, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, latitude, longitude, timestamp))
    c.execute("INSERT INTO location_history (user_id, latitude, longitude, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, latitude, longitude, timestamp))
    conn.commit()
    conn.close()
    emit('location_update', {**data, 'timestamp': timestamp}, room='dashboard')

if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)