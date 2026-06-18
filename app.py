from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
from datetime import date, timedelta
import calendar
 
app = Flask(__name__)
 
MET_VALUES = {
    'weights':          5.0,
    'stairmaster':      9.0,
    'tennis':           7.3,
    'run':              9.8,
    'long_run':         8.5,
    'intervals':        12.0,
    'walking':          3.5,
    'pickleball':       6.0,
    'swimming':         8.0,
    'bike':             7.5,
}

ACTIVITY_CATEGORY = {
    'weights':          'Weight Training',
    'stairmaster':      'Cardio',
    'tennis':           'Cardio',
    'run':              'Cardio',
    'long_run':         'Cardio',
    'intervals':        'Cardio',
    'walking':          'Cardio',
    'pickleball':       'Cardio',
    'swimming':         'Cardio',
    'bike':             'Cardio',
}
 
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="workout_tracker"
    )
 
def calculate_calories(exercise_type, duration, body_weight):
    met = MET_VALUES.get(exercise_type, 5.0)
    # Standard MET formula: calories = MET * weight(kg) * duration(hours)
    calories = met * body_weight * (duration / 60)
    return round(calories, 1)
 
# Home/Dashboard
@app.route("/")
def index():
    db = get_db()
    cursor = db.cursor(dictionary=True)
 
    today = date.today()
 
    # Get recent activities
    cursor.execute("SELECT * FROM workouts ORDER BY date DESC LIMIT 5")
    activities = cursor.fetchall()
 
    # Today's calories
    cursor.execute("SELECT SUM(calories) as total FROM workouts WHERE date = %s", (today,))
    result = cursor.fetchone()
    daily_calories = round(result['total'] or 0, 1)
 
    # Today's activity count
    cursor.execute("SELECT COUNT(*) as count FROM workouts WHERE date = %s", (today,))
    today_count = cursor.fetchone()['count']
 
    # Weekly stats (last 7 days)
    week_ago = today - timedelta(days=7)
 
    cursor.execute("SELECT COUNT(*) as count FROM workouts WHERE date >= %s", (week_ago,))
    weekly_count = cursor.fetchone()['count']
 
    cursor.execute("SELECT SUM(calories) as total FROM workouts WHERE date >= %s", (week_ago,))
    result = cursor.fetchone()
    weekly_calories = round(result['total'] or 0, 1)
 
    cursor.execute("SELECT SUM(distance) as total FROM workouts WHERE date >= %s AND distance IS NOT NULL", (week_ago,))
    result = cursor.fetchone()
    weekly_km = round(result['total'] or 0, 1)
 
    cursor.close()
    db.close()
 
    return render_template("index.html",
        activities=activities,
        daily_calories=daily_calories,
        today_count=today_count,
        weekly_count=weekly_count,
        weekly_calories=weekly_calories,
        weekly_km=weekly_km,
        today=today
    )
 
# Log Activity (unified)
@app.route("/log", methods=["GET", "POST"])
def log():
    if request.method == "POST":
        exercise_type = request.form["exercise_type"]
        exercise_name = request.form.get("exercise_name") or exercise_type.title()
        duration = int(request.form["duration"])
        body_weight = float(request.form.get("body_weight", 70))
        activity_date = request.form["date"]
 
        # Weights specific fields
        num_sets = request.form.get("num_sets") or None
        reps = request.form.get("reps") or None
        weight = request.form.get("weight") or None
 
        # Running specific
        distance = request.form.get("distance") or None
 
        calories = calculate_calories(exercise_type, duration, body_weight)
        category = ACTIVITY_CATEGORY.get(exercise_type, 'Other')
 
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO workouts 
            (exercise, exercise_type, num_sets, reps, weight, duration, calories, date, body_weight, distance)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (exercise_name, category, num_sets, reps, weight, duration, calories, activity_date, body_weight, distance))
        db.commit()
        cursor.close()
        db.close()
        return redirect(url_for("index"))
 
    return render_template("log.html", today=date.today())
 
# Schedule
@app.route("/schedule", methods=["GET", "POST"])
def schedule():
    if request.method == "POST":
        day = request.form["day"]
        exercise = request.form["exercise"]
        notes = request.form["notes"]
 
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO schedule (day, exercise, notes) VALUES (%s, %s, %s)",
            (day, exercise, notes)
        )
        db.commit()
        cursor.close()
        db.close()
        return redirect(url_for("schedule"))
 
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM schedule ORDER BY FIELD(day, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')")
    scheduled = cursor.fetchall()
    cursor.close()
    db.close()
 
    return render_template("schedule.html", scheduled=scheduled)
 
# Calendar
@app.route("/calendar")
@app.route("/calendar/<int:year>/<int:month>")
def calendar_view(year=None, month=None):
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month
 
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
 
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
 
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
 
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM workouts WHERE MONTH(date) = %s AND YEAR(date) = %s", (month, year))
    activities = cursor.fetchall()
    cursor.close()
    db.close()
 
    activity_map = {}
    for a in activities:
        day = a['date'].day
        if day not in activity_map:
            activity_map[day] = []
        activity_map[day].append(a)
 
    return render_template("calendar.html",
        cal=cal,
        month_name=month_name,
        year=year,
        month=month,
        today=today,
        activity_map=activity_map,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year
    )
 
# Mark schedule item complete
@app.route("/complete/<int:id>")
def complete(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE schedule SET completed = TRUE WHERE id = %s", (id,))
    db.commit()
    cursor.close()
    db.close()
    return redirect(url_for("schedule"))
 
# Delete schedule item
@app.route("/delete_schedule/<int:id>")
def delete_schedule(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM schedule WHERE id = %s", (id,))
    db.commit()
    cursor.close()
    db.close()
    return redirect(url_for("schedule"))
 
# Delete activity
@app.route("/delete/<int:id>")
def delete(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM workouts WHERE id = %s", (id,))
    db.commit()
    cursor.close()
    db.close()
    return redirect(url_for("index"))
 
if __name__ == "__main__":
    app.run(debug=True)
 