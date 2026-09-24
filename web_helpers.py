"""Shared authentication and database lookup helpers for web routes."""
from functools import wraps
from flask import abort, flash, redirect, request, session, url_for
from database import db
from models import Match, RideRequest


def login_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)
    return wrapped


def get_owned_ride(ride_id):
    ride = db.session.get(RideRequest, ride_id)
    if not ride or ride.user_id != session["user_id"]:
        abort(404)
    return ride


def get_active_ride():
    return (
        RideRequest.query.filter_by(user_id=session["user_id"])
        .filter(RideRequest.status.in_(["waiting", "matched"]))
        .order_by(RideRequest.created_at.desc())
        .first()
    )


def get_participant_match(match_id):
    match = db.session.get(Match, match_id)
    participant_ids = (match.ride_1.user_id, match.ride_2.user_id) if match else ()
    if not match or session["user_id"] not in participant_ids:
        abort(404)
    return match
