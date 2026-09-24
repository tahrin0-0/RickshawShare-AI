"""Database models for accounts, ride requests, and matches."""
from datetime import datetime, timezone

from database import db


def utc_now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    gender = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    rides = db.relationship("RideRequest", back_populates="user")


class RideRequest(db.Model):
    __tablename__ = "ride_requests"
    __table_args__ = (
        db.CheckConstraint("status IN ('waiting','matched','completed','cancelled')"),
    )

    ride_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    pickup_name = db.Column(db.String(255), nullable=False)
    pickup_latitude = db.Column(db.Float, nullable=False)
    pickup_longitude = db.Column(db.Float, nullable=False)
    destination_name = db.Column(db.String(255), nullable=False)
    destination_latitude = db.Column(db.Float, nullable=False)
    destination_longitude = db.Column(db.Float, nullable=False)
    preferred_time = db.Column(db.DateTime, nullable=False, index=True)
    gender_preference = db.Column(db.String(30), nullable=False, default="any")
    status = db.Column(db.String(20), nullable=False, default="waiting", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    user = db.relationship("User", back_populates="rides")


class Match(db.Model):
    __tablename__ = "matches"
    __table_args__ = (
        db.CheckConstraint("ride_1_id <> ride_2_id"),
        db.CheckConstraint("status IN ('pending','accepted','rejected','cancelled','completed')"),
    )

    match_id = db.Column(db.Integer, primary_key=True)
    ride_1_id = db.Column(db.Integer, db.ForeignKey("ride_requests.ride_id"), nullable=False, index=True)
    ride_2_id = db.Column(db.Integer, db.ForeignKey("ride_requests.ride_id"), nullable=False, index=True)
    match_probability = db.Column(db.Float, nullable=False)
    pickup_distance_km = db.Column(db.Float, nullable=False)
    time_difference_min = db.Column(db.Float, nullable=False)
    route_overlap_percent = db.Column(db.Float, nullable=False)
    destination_compatibility = db.Column(db.Float, nullable=False)
    estimated_detour_km = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    ride_1 = db.relationship("RideRequest", foreign_keys=[ride_1_id])
    ride_2 = db.relationship("RideRequest", foreign_keys=[ride_2_id])
