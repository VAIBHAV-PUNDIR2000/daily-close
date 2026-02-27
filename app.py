import os
import smtplib
import ssl
from datetime import datetime, date, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_sqlalchemy import SQLAlchemy

IST = ZoneInfo("Asia/Kolkata")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "daily-close-dev")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///daily_close.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

APP_EMAIL = os.getenv("APP_EMAIL", "vaibhavpundir29@gmail.com")
APP_PASSWORD = os.getenv("APP_PASSWORD", "dailyclose")
REMINDER_EMAIL = os.getenv("REMINDER_EMAIL", "vaibhavpundir29@gmail.com")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(280), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="open")
    day_key = db.Column(db.String(10), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)


class DailyStat(db.Model):
    day_key = db.Column(db.String(10), primary_key=True)
    nudge_sent = db.Column(db.Boolean, default=False)


def now_ist():
    return datetime.now(IST)


def today_key():
    return now_ist().date().isoformat()


def day_bounds(d: date):
    start = datetime(d.year, d.month, d.day, tzinfo=IST)
    end = start + timedelta(days=1)
    return start, end


def login_required():
    return session.get("user") == APP_EMAIL


@app.before_request
def enforce_login():
    open_routes = {"login", "static", "healthz"}
    if request.endpoint in open_routes or request.path.startswith("/api/manifest"):
        return
    if not login_required():
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if email == APP_EMAIL.lower() and password == APP_PASSWORD:
            session["user"] = APP_EMAIL
            return redirect(url_for("index"))
        error = "Invalid credentials"
    return render_template("login.html", app_email=APP_EMAIL, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    dk = today_key()
    tasks = Task.query.filter_by(day_key=dk).order_by(Task.created_at.desc()).all()
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "closed")
    pending = total - completed
    pct = int((completed / total) * 100) if total else 0

    message = None
    if total > 0 and pending == 0:
        message = "All tasks closed. Solid day. 🔥"
    elif total >= 8 and pending >= 5:
        message = "You’re carrying a lot today. Consider reducing daily load for better closure."

    return render_template("index.html", tasks=tasks, total=total, completed=completed, pending=pending, pct=pct, message=message)


@app.route("/api/manifest", methods=["POST"])
def manifest_task():
    title = (request.json.get("title", "") if request.is_json else request.form.get("title", "")).strip()
    if not title:
        return jsonify({"ok": False, "error": "Title required"}), 400

    ts = now_ist()
    task = Task(title=title, status="open", day_key=ts.date().isoformat(), created_at=ts)
    db.session.add(task)
    db.session.commit()
    return jsonify({"ok": True, "id": task.id, "title": task.title})


@app.route("/api/task/<int:task_id>/toggle", methods=["POST"])
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.status == "open":
        task.status = "closed"
        task.completed_at = now_ist()
    else:
        task.status = "open"
        task.completed_at = None
    db.session.commit()
    return jsonify({"ok": True, "status": task.status})


@app.route("/dashboard")
def dashboard():
    today = date.today()
    today_dk = today_key()

    today_tasks = Task.query.filter_by(day_key=today_dk).all()
    tt = len(today_tasks)
    tc = sum(1 for t in today_tasks if t.status == "closed")
    tp = tt - tc
    tpct = int((tc / tt) * 100) if tt else 0

    weekly = []
    streak = 0
    longest = 0
    run = 0
    for i in range(6, -1, -1):
        d = now_ist().date() - timedelta(days=i)
        dk = d.isoformat()
        day_tasks = Task.query.filter_by(day_key=dk).all()
        total = len(day_tasks)
        closed = sum(1 for t in day_tasks if t.status == "closed")
        pct = int((closed / total) * 100) if total else 0
        weekly.append({"day": d.strftime("%a"), "date": dk, "total": total, "closed": closed, "pct": pct})

    history_days = sorted({t.day_key for t in Task.query.all()}, reverse=True)[:30]
    history = []
    for dk in history_days:
        day_tasks = Task.query.filter_by(day_key=dk).all()
        total = len(day_tasks)
        closed = sum(1 for t in day_tasks if t.status == "closed")
        pct = int((closed / total) * 100) if total else 0
        history.append({"day": dk, "total": total, "closed": closed, "pct": pct})

    # streaks (consecutive days with 100% closure and at least one task)
    sorted_days = sorted(history_days)
    for dk in sorted_days:
        day_tasks = Task.query.filter_by(day_key=dk).all()
        total = len(day_tasks)
        closed = sum(1 for t in day_tasks if t.status == "closed")
        if total > 0 and closed == total:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    streak = 0
    d = now_ist().date()
    while True:
        dk = d.isoformat()
        day_tasks = Task.query.filter_by(day_key=dk).all()
        if not day_tasks:
            break
        total = len(day_tasks)
        closed = sum(1 for t in day_tasks if t.status == "closed")
        if total > 0 and closed == total:
            streak += 1
            d -= timedelta(days=1)
        else:
            break

    return render_template(
        "dashboard.html",
        today_stats={"total": tt, "completed": tc, "pending": tp, "pct": tpct},
        weekly=weekly,
        history=history,
        streak=streak,
        longest=longest,
    )


@app.route("/export/weekly.csv")
def export_weekly():
    import csv
    from io import StringIO, BytesIO

    data = StringIO()
    writer = csv.writer(data)
    writer.writerow(["date", "total_tasks", "completed", "completion_pct"])
    for i in range(6, -1, -1):
        d = now_ist().date() - timedelta(days=i)
        dk = d.isoformat()
        day_tasks = Task.query.filter_by(day_key=dk).all()
        total = len(day_tasks)
        closed = sum(1 for t in day_tasks if t.status == "closed")
        pct = int((closed / total) * 100) if total else 0
        writer.writerow([dk, total, closed, pct])
    mem = BytesIO(data.getvalue().encode("utf-8"))
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="daily-close-weekly.csv")


@app.route("/healthz")
def healthz():
    return {"ok": True}


def _send_email(subject: str, body: str):
    if not SMTP_USER or not SMTP_PASS:
        print("SMTP not configured; skipping email")
        return
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = REMINDER_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


def daily_reminder():
    dk = today_key()
    tasks = Task.query.filter_by(day_key=dk, status="open").order_by(Task.created_at.asc()).all()
    if not tasks:
        body = "All tasks closed. Solid day. 🔥"
    else:
        items = "\n".join([f"• {t.title}" for t in tasks])
        body = f"You have {len(tasks)} pending tasks:\n{items}\n\nClose your day strong 💪"
    _send_email("Daily Close Reminder", body)


def noon_nudge():
    dk = today_key()
    stat = DailyStat.query.get(dk)
    if stat and stat.nudge_sent:
        return
    count = Task.query.filter_by(day_key=dk).count()
    if count == 0:
        _send_email("Daily Close Nudge", "No tasks manifested yet today. Add your first task and build momentum 🚀")
        if not stat:
            stat = DailyStat(day_key=dk, nudge_sent=True)
            db.session.add(stat)
        else:
            stat.nudge_sent = True
        db.session.commit()


def sunday_summary():
    lines = ["Weekly Daily Close Summary", ""]
    total_all = 0
    closed_all = 0
    for i in range(6, -1, -1):
        d = now_ist().date() - timedelta(days=i)
        dk = d.isoformat()
        day_tasks = Task.query.filter_by(day_key=dk).all()
        total = len(day_tasks)
        closed = sum(1 for t in day_tasks if t.status == "closed")
        total_all += total
        closed_all += closed
        pct = int((closed / total) * 100) if total else 0
        lines.append(f"{dk}: {closed}/{total} ({pct}%)")
    score = int((closed_all / total_all) * 100) if total_all else 0
    lines.append("")
    lines.append(f"Weekly productivity score: {score}")
    _send_email("Daily Close Weekly Summary", "\n".join(lines))


def start_scheduler():
    scheduler = BackgroundScheduler(timezone=IST)
    scheduler.add_job(daily_reminder, "cron", hour=15, minute=0, id="reminder_1500", replace_existing=True)
    scheduler.add_job(daily_reminder, "cron", hour=18, minute=0, id="reminder_1800", replace_existing=True)
    scheduler.add_job(daily_reminder, "cron", hour=21, minute=0, id="reminder_2100", replace_existing=True)
    scheduler.add_job(noon_nudge, "cron", hour=12, minute=0, id="nudge_1200", replace_existing=True)
    scheduler.add_job(sunday_summary, "cron", day_of_week="sun", hour=21, minute=30, id="weekly_summary", replace_existing=True)
    scheduler.start()


with app.app_context():
    db.create_all()

if os.getenv("ENABLE_SCHEDULER", "1") == "1":
    with app.app_context():
        start_scheduler()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
