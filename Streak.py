def calculate_streak(habit):
    try:
        activities = Activity.query.filter_by(habit_id=habit.id).order_by(Activity.completed_at.desc()).all()
        if not activities:
            return 0
        streak = 0
        today = datetime.utcnow().date()
        for i, activity in enumerate(activities):
            activity_date = activity.completed_at.date()
            if i == 0 and activity_date < today:
                return streak
            if i > 0 and (activities[i-1].completed_at.date() - activity_date).days > 1:
                break
            streak += 1
        return streak
    except SQLAlchemyError as e:
        logger.error(f"Database error calculating streak: {str(e)}")
        return 0