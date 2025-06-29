from flask import request, jsonify
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
import logging

from . import app, db
from .models import Habit, Activity
from .auth import token_required

logger = logging.getLogger(__name__)

@app.route("/api/habits/analysis", methods=["GET", "OPTIONS"])
@token_required
def get_analysis(user):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    try:
        habits = Habit.query.filter_by(user_id=user.id).all()
        habit_data = []
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        trend_labels = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(31)]
        trend_data = {habit.id: [0] * 31 for habit in habits}

        for habit in habits:
            total_activities = Activity.query.filter_by(habit_id=habit.id).count()
            if habit.frequency == "daily":
                expected_days = 30
                actual_days = db.session.query(
                    func.count(func.distinct(func.date(Activity.completed_at)))
                ).filter(
                    Activity.habit_id == habit.id,
                    Activity.completed_at >= start_date,
                    Activity.completed_at <= end_date
                ).scalar() or 0
                completion_rate = actual_days / expected_days if expected_days > 0 else 0
            else:
                expected_weeks = 4
                actual_weeks = db.session.query(
                    func.count(func.distinct(func.extract("week", Activity.completed_at)))
                ).filter(
                    Activity.habit_id == habit.id,
                    Activity.completed_at >= start_date,
                    Activity.completed_at <= end_date
                ).scalar() or 0
                completion_rate = actual_weeks / expected_weeks if expected_weeks > 0 else 0

            activities = Activity.query.filter(
                Activity.habit_id == habit.id,
                Activity.completed_at >= start_date,
                Activity.completed_at <= end_date
            ).all()
            for activity in activities:
                day_index = (activity.completed_at.date() - start_date.date()).days
                if 0 <= day_index < 31:
                    trend_data[habit.id][day_index] += 1

            habit_data.append({
                "id": habit.id,
                "name": habit.name,
                "frequency": habit.frequency,
                "total_activities": total_activities,
                "completion_rate": completion_rate
            })

        logger.debug(f"Analysis fetched for user {user.username}: {len(habit_data)} habits")
        return jsonify({
            "habits": habit_data,
            "trends": {
                "labels": trend_labels,
                "data": trend_data
            }
        }), 200
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching analysis: {str(e)}")
        return jsonify({"message": "Failed to fetch analysis"}), 500