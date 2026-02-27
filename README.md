# Daily Close

Daily manifestation + closure productivity web app.

## Features
- Instant task capture from homepage (enter to save)
- Daily separation using Asia/Kolkata day key
- Open/Close task with completion timestamps
- Reminder emails at 3PM, 6PM, 9PM IST
- Noon nudge if no tasks by 12PM
- Dashboard: today stats, weekly chart, streaks, history
- Weekly CSV export
- PWA basics (manifest + service worker)

## Local run
```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```
Open: http://127.0.0.1:5000

## Deployment (Render free)
1. Push this folder to GitHub.
2. Create new Render Blueprint using `render.yaml`.
3. Set env vars:
   - APP_PASSWORD
   - SMTP_USER
   - SMTP_PASS
4. Deploy.

## Reminder scheduling
APScheduler runs in app process at IST:
- 12:00 nudge
- 15:00 reminder
- 18:00 reminder
- 21:00 reminder
- Sunday 21:30 weekly summary

## Change reminder times
Edit `start_scheduler()` in `app.py` cron lines.

## Architecture
- Flask app + server-rendered templates
- SQLite via SQLAlchemy
- APScheduler in-process jobs
- SMTP email delivery

## Scale beyond free tier
- Move DB to Postgres (Neon/Supabase)
- Move scheduler to worker/cron service
- Add Redis queue for notifications
- Add multi-user auth
