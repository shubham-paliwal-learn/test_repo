#!/usr/bin/env bash
# Start a Celery worker for the TMA background jobs.
set -e
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
celery -A app.tasks.celery_app worker --loglevel=info --pool=solo
