import os
import logging
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv
import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
try:
    from models import db, User, Habit, Activity
except ImportError:
    # Dummy fallback for code completion/testing
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
    class User: pass
    class Habit: pass
    class Activity: pass

try:
    from config import Config
except ImportError:
    class Config:
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

frontend_url = os.getenv('FRONTEND_URL', 'https://front-lovat-eight.vercel.app')
if not frontend_url:
    logger.error("FRONTEND_URL environment variable is not set")
    raise ValueError("FRONTEND_URL environment variable is required")

CORS(app, resources={
    r"/api/*": {
        "origins": ["https://front-lovat-eight.vercel.app", "http://localhost:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Authorization", "Content-Type"],
        "supports_credentials": True,
        "expose_headers": ["Authorization"]
    }
})

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Dummy implementation for demonstration; replace with real JWT logic
        class DummyUser:
            id = 1
            username = "testuser"
        return f(DummyUser(), *args, **kwargs)
    return decorated

def calculate_streak(habit):
    # Dummy streak calculation; replace with real logic as needed
    return 0

@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        response = jsonify({"status": "preflight accepted"})
        response.headers.add("Access-Control-Allow-Origin", "https://front-lovat-eight.vercel.app")
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Authorization, Content-Type")
        return response

db.init_app(app)
migrate = Migrate(app, db)

@app.route("/api/habits", methods=["GET", "POST", "OPTIONS"])
@token_required
def habits(user):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if request.method == "GET":
        try:
            habits = Habit.query.filter_by(user_id=user.id).all()
            logger.debug(f"Fetched {len(habits)} habits for user {user.username}")
            return jsonify([{
                "id": habit.id,
                "name": habit.name,
                "description": habit.description,
                "frequency": habit.frequency,
                "streak": calculate_streak(habit)
            } for habit in habits]), 200
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching habits: {str(e)}")
            return jsonify({"message": "Failed to fetch habits"}), 500
    if request.method == "POST":
        data = request.get_json()
        logger.debug(f"Create habit payload: {data}")
        name = data.get("name")
        description = data.get("description", "")
        frequency = data.get("frequency")
        if not name or not frequency:
            logger.error("Missing name or frequency")
            return jsonify({"message": "Name and frequency required"}), 400
        if frequency.lower() not in ["daily", "weekly"]:
            logger.error(f"Invalid frequency: {frequency}")
            return jsonify({"message": "Frequency must be 'daily' or 'weekly'"}), 400
        try:
            new_habit = Habit(name=name, description=description, frequency=frequency.lower(), user_id=user.id)
            db.session.add(new_habit)
            db.session.commit()
            logger.info(f"Habit created: {name} for user {user.username}")
            return jsonify({"message": "Habit created", "id": new_habit.id}), 201
        except SQLAlchemyError as e:
            logger.error(f"Database error creating habit: {str(e)}")
            db.session.rollback()
            return jsonify({"message": "Failed to create habit"}), 500

@app.route("/api/habits/<int:id>", methods=["PUT", "DELETE", "OPTIONS"])
@token_required
def habit(user, id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    habit = Habit.query.get_or_404(id)
    if habit.user_id != user.id:
        logger.error(f"Unauthorized access to habit {id} by user {user.id}")
        return jsonify({"message": "Unauthorized"}), 403
    if request.method == "PUT":
        data = request.get_json()
        logger.debug(f"Update habit {id} payload: {data}")
        frequency = data.get("frequency", habit.frequency)
        if frequency.lower() not in ["daily", "weekly"]:
            logger.error(f"Invalid frequency: {frequency}")
            return jsonify({"message": "Frequency must be 'daily' or 'weekly'"}), 400
        try:
            habit.name = data.get("name", habit.name)
            habit.description = data.get("description", habit.description)
            habit.frequency = frequency.lower()
            db.session.commit()
            logger.info(f"Habit {id} updated for user {user.username}")
            return jsonify({"message": "Habit updated"}), 200
        except SQLAlchemyError as e:
            logger.error(f"Database error updating habit: {str(e)}")
            db.session.rollback()
            return jsonify({"message": "Failed to update habit"}), 500
    if request.method == "DELETE":
        try:
            logger.info(f"Deleting habit {id} for user {user.id}")
            db.session.delete(habit)
            db.session.commit()
            logger.info(f"Habit {id} deleted successfully by user {user.id}")
            return jsonify({"message": "Habit deleted"}), 200
        except SQLAlchemyError as e:
            logger.error(f"Error deleting habit {id}: {str(e)}")
            db.session.rollback()
            return jsonify({"message": "Failed to delete habit"}), 500

@app.route("/api/habits/<int:id>/log", methods=["POST", "OPTIONS"])
@token_required
def log_activity(user, id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    habit = Habit.query.get_or_404(id)
    if habit.user_id != user.id:
        logger.error(f"Unauthorized access to habit {id} by user {user.id}")
        return jsonify({"message": "Unauthorized"}), 403
    try:
        new_activity = Activity(habit_id=id, user_id=user.id, completed_at=datetime.utcnow())
        db.session.add(new_activity)
        db.session.commit()
        logger.info(f"Activity logged for habit {id} by user {user.username}")
        return jsonify({"message": "Activity logged", "streak": calculate_streak(habit)}), 201
    except SQLAlchemyError as e:
        logger.error(f"Database error logging activity: {str(e)}")
        db.session.rollback()
        return jsonify({"message": "Failed to log activity"}), 500

@app.route("/api/habits/<int:id>/history", methods=["GET", "OPTIONS"])
@token_required
@app.route("/api/habits/<int:id>/history", methods=["GET", "OPTIONS"])
@token_required
def get_history(user, id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    habit = Habit.query.get_or_404(id)
    if habit.user_id != user.id:
        logger.error(f"Unauthorized access to habit {id} by user {user.id}")
        return jsonify({"message": "Unauthorized"}), 403
    try:
        activities = Activity.query.filter_by(habit_id=id).order_by(Activity.completed_at.desc()).all()
        logger.debug(f"Fetched history for habit {id}: {len(activities)} activities")
        return jsonify([
            {
                "id": activity.id,
                "completed_at": activity.completed_at.isoformat()
            } for activity in activities
        ]), 200
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching history: {str(e)}")
        return jsonify({"message": "Failed to fetch history"}), 500