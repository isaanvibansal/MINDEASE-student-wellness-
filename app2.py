from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, date
from bson import ObjectId
import os
import json
from journal_api import create_journal_blueprint
from music_recommender import create_music_blueprint
from chatbot import create_chatbot_blueprint

# MongoDB
client = MongoClient(os.environ.get("MONGO_URI"))
db = client["mindease"]
users_collection = db["users"]

print("✅ Mongo connected")

# Flask
app = Flask(__name__)
# Register MindEase AI Chatbot
app.register_blueprint(create_chatbot_blueprint(db))

# 🔐 SESSION SECRET KEY
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "mindease-local-secret-key-2026"
)
app.register_blueprint(create_journal_blueprint(db))
app.register_blueprint(create_music_blueprint())

@app.route("/check")
def check():
    return "SERVER WORKING"

# ---------------- TEMP STORAGE ----------------
moods = []
journals = []

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("app.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        print("🔥 Signup route triggered")
        print("Username:", username)

        # Check if user already exists
        existing_user = users_collection.find_one({
            "username": username
        })

        if existing_user:
            return "Username already exists ❌"

        # Create new user
        users_collection.insert_one({
            "username": username,
            "password": password,
            "login_count": 0,
            "last_login": None,
            "created_at": datetime.now()
        })

        print("✅ New user created")

        return redirect(url_for("login"))

    return render_template("signup.html")
    
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        print("🔐 Login attempt")
        print("Username:", username)

        # Find user by username
        user = users_collection.find_one({
            "username": username
        })

        print("User found:", user)

        if user and user["password"] == password:

            # Update login information in MongoDB
            users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "last_login": datetime.now()
                    },
                    "$inc": {
                        "login_count": 1
                    }
                }
            )

            print("✅ Login successful")
            print("📊 Login count updated")

            # Store user in session
            session["user"] = username

            return redirect(url_for("dashboard"))

        else:

            print("❌ Invalid credentials")

            return "Invalid credentials ❌"

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    from flask import session
    session.pop("user", None) # 👈 Forget the user
    return redirect(url_for("home"))



# ---------------- MOOD PAGE ----------------

@app.route("/mood")
def mood():

    mood = request.args.get("selected_mood", "")

    bg = "#e0f7fa"

    if mood == "happy":
        bg = "#FFF8D6"

    elif mood == "angry":
        bg = "#FFDADA"

    elif mood == "sad":
        bg = "#DCE8FF"

    elif mood == "stressed":
        bg = "#F4E6FF"

    return render_template(
        "moodtracker.html",
        name=session.get("user","Guest"),
        bg=bg
    )


# ---------------- SAVE MOOD ----------------

@app.route("/save_mood", methods=["POST"])
def save_mood():

    mood = request.form.get("mood")

    mood_entry = {
        "username": session.get("user", "Guest"),
        "mood": mood,
        "time": datetime.now().strftime("%B %d, %Y - %I:%M %p")
    }

    db["moods"].insert_one(mood_entry)

    return redirect(url_for("music", mood=mood))


# ---------------- JOURNAL PAGE ----------------
@app.route("/journal")
def journal():
    return render_template("journal.html")

# ---------------- SAVE JOURNAL (No JS Version) ----------------
@app.route("/save_journal", methods=["POST"])
def save_journal():
    from flask import session
    
    # This is how we get data from a standard HTML form
    left_content = request.form.get("leftText")
    right_content = request.form.get("rightText")
    
    username = session.get("user", "Guest")
    full_text = f"{left_content} | {right_content}"

    entry = {
        "username": username,
        "text": full_text,
        "date": datetime.now().strftime("%B %d, %Y - %I:%M %p")
    }

    # Save to MongoDB
    db["journals"].insert_one(entry)

    # Instead of an alert, we just redirect directly to the history page
    return redirect(url_for("journal_history"))


# ---------------- GET JOURNALS ----------------
@app.route("/journal_history")
def journal_history():

    username = session.get("user", "Guest")

    user_entries = list(
        db["journals"]
        .find({"username": username})
        .sort("_id", -1)
    )

    return render_template(
        "journal_history.html",
        entries=user_entries
    )

# ---------------- MUSIC PAGE ----------------
@app.route("/music")
@app.route("/music/<mood>")
def music(mood="happy"):

    spotify_playlists = {

        "happy": {
            "English 🎵": "0jrlHA5UmxRxJjoykf7qRY",
            "Hindi ✌🏻": "37i9dQZF1DWTwbZHrJRIgD",
            "Punjabi🕺🏻": "0xawH3WmFz4PdLGYYn3gpT",
            "South Indian 🎶": "0dPzC4kI939RwZFiMHHDHl"
        },

        "sad": {
            "English Mood Booster": "37i9dQZF1DX3rxVfibe1L0",
            "Hindi Mood Booster": "37i9dQZF1DX5q67ZpWyRrZ",
            "South Indian Feel Good 🌸": "3NF0iDKGPhSfB5tfRpkVlQ"
        },

        "stressed": {
            "Nature Sounds 🌧️": "37i9dQZF1DX4PP3DA4J0N8",
            "Relaxation 🌿": "37i9dQZF1DXebxttQCq0zA",
            "Devotional 🕉️": "7gFVfcFKRzeOH1cfhVdj0A",
            "Instrumental 🎹": "37i9dQZF1DX4sWSpwq3LiO"
        },

        "angry": {
            "Calm Down 🌊": "37i9dQZF1DWU0ScTcjJBdj",
            "Lo-fi ☕": "37i9dQZF1DWYoYGBbGKurt",
            "Meditation 🧘": "37i9dQZF1DWZqd5JICZI0u"
        }

    }

    playlists = spotify_playlists.get(
        mood.lower(),
        spotify_playlists["happy"]
    )

    return render_template(
        "music.html",
        playlists=playlists,
        current_mood=mood
    )


# ---------------- INSIGHTS PAGE (OPTIMIZED) ----------------
from collections import Counter

@app.route("/insights")
def insights():

    username = session.get("user", "Guest")

    user_journals = list(
        db["journals"].find({"username": username}).sort("_id", -1)
    )

    j_count = len(user_journals)

    m_count = db["moods"].count_documents({"username": username})

    weekly_moods = list(
        db["moods"]
        .find({"username": username})
        .sort("_id", -1)
        .limit(7)
    )

    mood_names = [m["mood"] for m in weekly_moods]

    if mood_names:
        most_mood = Counter(mood_names).most_common(1)[0][0]
    else:
        most_mood = None

    return render_template(
        "insights.html",
        journals=user_journals,
        j_count=j_count,
        m_count=m_count,
        weekly_moods=weekly_moods,
        most_mood=most_mood
    )


@app.route("/breathing")
def breathing():
    # Require the user to log in first
    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("breathing.html")


# ---------------- ACADEMIC STRESS PLANNER ----------------

study_tasks = db["study_tasks"]


def planner_login_required():
    """Return True when a user is logged in."""
    return bool(session.get("user"))


@app.route("/planner")
def planner():
    if not planner_login_required():
        return redirect(url_for("login"))

    username = session["user"]
    today = date.today().isoformat()

    tasks = list(
        study_tasks.find({"username": username})
        .sort([("completed", 1), ("due_date", 1), ("created_at", -1)])
    )

    total = len(tasks)
    completed_count = sum(1 for task in tasks if task.get("completed"))
    pending_count = total - completed_count
    overdue_count = sum(
        1 for task in tasks
        if not task.get("completed")
        and task.get("due_date")
        and task["due_date"] < today
    )

    return render_template(
        "planner.html",
        tasks=tasks,
        today=today,
        total=total,
        completed_count=completed_count,
        pending_count=pending_count,
        overdue_count=overdue_count
    )


@app.route("/planner/add", methods=["POST"])
def planner_add():
    if not planner_login_required():
        return redirect(url_for("login"))

    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    due_date = request.form.get("due_date", "").strip()
    priority = request.form.get("priority", "medium").lower()
    task_type = request.form.get("task_type", "assignment").lower()
    minutes_raw = request.form.get("estimated_minutes", "30").strip()

    if not title or len(title) > 120:
        return "Please enter a task title (maximum 120 characters).", 400

    if len(subject) > 80:
        return "Subject must be 80 characters or fewer.", 400

    try:
        if due_date:
            date.fromisoformat(due_date)

        estimated_minutes = int(minutes_raw)
        if not 5 <= estimated_minutes <= 600:
            raise ValueError
    except ValueError:
        return "Please enter a valid date and a study duration between 5 and 600 minutes.", 400

    if priority not in {"low", "medium", "high"}:
        priority = "medium"

    if task_type not in {"assignment", "exam", "revision", "project", "other"}:
        task_type = "assignment"

    study_tasks.insert_one({
        "username": session["user"],
        "title": title,
        "subject": subject,
        "due_date": due_date,
        "priority": priority,
        "task_type": task_type,
        "estimated_minutes": estimated_minutes,
        "completed": False,
        "created_at": datetime.utcnow()
    })

    return redirect(url_for("planner"))


@app.route("/planner/toggle/<task_id>", methods=["POST"])
def planner_toggle(task_id):
    if not planner_login_required():
        return redirect(url_for("login"))

    try:
        object_id = ObjectId(task_id)
    except Exception:
        return "Invalid task ID.", 400

    task = study_tasks.find_one({
        "_id": object_id,
        "username": session["user"]
    })

    if task:
        study_tasks.update_one(
            {
                "_id": object_id,
                "username": session["user"]
            },
            {"$set": {"completed": not task.get("completed", False)}}
        )

    return redirect(url_for("planner"))


@app.route("/planner/delete/<task_id>", methods=["POST"])
def planner_delete(task_id):
    if not planner_login_required():
        return redirect(url_for("login"))

    try:
        object_id = ObjectId(task_id)
    except Exception:
        return "Invalid task ID.", 400

    study_tasks.delete_one({
        "_id": object_id,
        "username": session["user"]
    })

    return redirect(url_for("planner"))


# ---------------- STUDY SESSION + STRESS CHECK-IN ----------------

study_sessions = db["study_sessions"]


@app.route("/study-session")
def study_session():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]

    # Only show this student's tasks.
    tasks = list(
        study_tasks.find({"username": username})
        .sort("due_date", 1)
    )

    # Resume an unfinished session if one is requested.
    active_id = request.args.get("active")
    active_session = None

    if active_id:
        try:
            active_session = study_sessions.find_one({
                "_id": ObjectId(active_id),
                "username": username,
                "completed": False
            })
        except Exception:
            active_session = None

    history = list(
        study_sessions.find({
            "username": username,
            "completed": True
        }).sort("finished_at", -1).limit(20)
    )

    for item in history:
        before = item.get("stress_before")
        after = item.get("stress_after")
        item["stress_change"] = (
            before - after
            if isinstance(before, int) and isinstance(after, int)
            else None
        )

    return render_template(
        "study_session.html",
        tasks=tasks,
        active_session=active_session,
        history=history
    )


@app.route("/study-session/start", methods=["POST"])
def start_study_session():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]

    try:
        stress_before = int(request.form.get("stress_before", ""))
        duration = int(request.form.get("duration", "25"))
    except (TypeError, ValueError):
        return "Enter a valid stress rating and session duration.", 400

    if not 1 <= stress_before <= 10:
        return "Stress rating must be between 1 and 10.", 400

    if duration not in {15, 25, 45, 60}:
        return "Choose a supported session duration.", 400

    task_id = request.form.get("task_id", "").strip()
    task_title = "Independent study"

    if task_id:
        try:
            task = study_tasks.find_one({
                "_id": ObjectId(task_id),
                "username": username
            })
        except Exception:
            task = None

        if not task:
            return "The selected task was not found.", 400

        task_title = task["title"]

    result = study_sessions.insert_one({
        "username": username,
        "task_id": task_id or None,
        "task_title": task_title,
        "duration_minutes": duration,
        "stress_before": stress_before,
        "stress_after": None,
        "reflection": "",
        "started_at": datetime.utcnow(),
        "finished_at": None,
        "completed": False
    })

    return redirect(url_for(
        "study_session",
        active=str(result.inserted_id)
    ))


@app.route("/study-session/finish/<session_id>", methods=["POST"])
def finish_study_session(session_id):
    if "user" not in session:
        return redirect(url_for("login"))

    try:
        object_id = ObjectId(session_id)
        stress_after = int(request.form.get("stress_after", ""))
    except (TypeError, ValueError):
        return "Invalid session or stress rating.", 400

    if not 1 <= stress_after <= 10:
        return "Stress rating must be between 1 and 10.", 400

    reflection = request.form.get("reflection", "").strip()[:500]

    result = study_sessions.update_one(
        {
            "_id": object_id,
            "username": session["user"],
            "completed": False
        },
        {
            "$set": {
                "stress_after": stress_after,
                "reflection": reflection,
                "finished_at": datetime.utcnow(),
                "completed": True
            }
        }
    )

    if result.matched_count == 0:
        return "Session not found or already completed.", 404

    # Update the linked task only if it belongs to this user.
    saved = study_sessions.find_one({
        "_id": object_id,
        "username": session["user"]
    })

    if saved and saved.get("task_id"):
        try:
            study_tasks.update_one(
                {
                    "_id": ObjectId(saved["task_id"]),
                    "username": session["user"]
                },
                {"$set": {"last_study_session": datetime.utcnow()}}
            )
        except Exception:
            pass

    return redirect(url_for("study_session"))

@app.route("/stress-buster")
def stress_buster():
    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("stress_buster.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)