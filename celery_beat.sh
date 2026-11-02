#!/usr/bin/env bash
# Start the Celery beat scheduler:
#   - daily reminders every day at REMINDER_HOUR (default 07:00 IST)
#   - monthly activity report on the 1st of every month at REPORT_HOUR
set -e
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
celery -A app.tasks.celery_app beat --loglevel=info
