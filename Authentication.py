import os
import logging
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from dotenv import load_dotenv
import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from models import db, User, Habit, Activity
from config import Config
from sqlalchemy import func

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
CORS(app, resources={r"/*": {
    "origins": os.getenv("FRONTEND_URL", "http://localhost:5173"),
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"]
}})
db.init_app(app)

# Create database tables
with app.app_context():
    db.create_all()

# JWT middleware
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            logger.error("Token missing in request")
            return jsonify({"message": "Token required"}), 401
        if token.startswith("Bearer "):
            token = token[7:]
        try:
            payload = jwt.decode(token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
            user = User.query.get(payload["user_id"])
            if not user:
                logger.error("User not found for token")
                return jsonify({"message": "Invalid token"}), 403
        except jwt.ExpiredJWTError:
            logger.error("Token expired")
            return jsonify({"message": "Token expired"}), 401
        except jwt.InvalidTokenError:
            logger.error("Invalid token")
            return jsonify({"message": "Invalid token"}), 401
        return f(user, *args, **kwargs)
    return decorated

# Register endpoint
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    if not username or not email or not password:
        return jsonify({"message": "Username, email, and password required"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username already exists"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already exists"}), 400
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    new_user = User(
        username=username,
        email=email,
        password=hashed_password.decode("utf-8")
    )
    db.session.add(new_user)
    db.session.commit()
    token = generate_token(new_user.id, new_user.email)
    return jsonify({"message": "User registered", "token": token}), 201

# Login endpoint
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    identifier = data.get("identifier")  # Can be username or email
    password = data.get("password")
    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
    if not user or not bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
        return jsonify({"message": "Invalid credentials"}), 401
    token = generate_token(user.id, user.email)
    return jsonify({"token": token, "username": user.username, "email": user.email}), 200

# Generate JWT
def generate_token(user_id, email):
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow()
    }
    token = jwt.encode(payload, app.config["JWT_SECRET_KEY"], algorithm="HS256")
    return token