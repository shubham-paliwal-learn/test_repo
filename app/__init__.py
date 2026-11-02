"""Trekking Management Application (TMA) - Flask API package.

Public entry point: ``python run.py`` (or ``flask --app app.main run``).
The SQLite database is created programmatically from the models in
``app.models`` and the single Admin account is bootstrapped after creation.
"""
from app.main import create_app

__all__ = ["create_app"]
