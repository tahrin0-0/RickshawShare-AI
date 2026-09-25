"""Dashboard, ride request, and match lifecycle routes."""
from datetime import datetime
from flask import abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import or_
from database import db
from matching_engine import find_matches
from models import Match, RideRequest
from web_helpers import get_active_ride, get_owned_ride, get_participant_match, login_required

COORDINATE_FIELDS = ("pickup_latitude", "pickup_longitude", "destination_latitude", "destination_longitude")


def _parse_ride_form():
    preferred_time = datetime.fromisoformat(request.form["preferred_time"])
    coordinates = {name: float(request.form[name]) for name in COORDINATE_FIELDS}
    if preferred_time < datetime.now():
        raise ValueError("Travel time must be in the future.")
    if not (-90 <= coordinates["pickup_latitude"] <= 90 and -90 <= coordinates["destination_latitude"] <= 90
            and -180 <= coordinates["pickup_longitude"] <= 180 and -180 <= coordinates["destination_longitude"] <= 180):
        raise ValueError("Invalid coordinates.")
    ride = RideRequest(
        user_id=session["user_id"], pickup_name=request.form["pickup_name"].strip(),
        destination_name=request.form["destination_name"].strip(), preferred_time=preferred_time,
        gender_preference=request.form["gender_preference"], **coordinates,
    )
    if not ride.pickup_name or not ride.destination_name:
        raise ValueError("Choose both locations on the map.")
    return ride


def _pending_match_for(ride):
    return (Match.query.filter(
        or_(Match.ride_1_id == ride.ride_id, Match.ride_2_id == ride.ride_id),
        Match.status.in_(["pending", "accepted"]),
    ).order_by(Match.created_at.desc()).first())


def _candidate_is_busy(ride_id, candidate_id):
    return Match.query.filter(
        Match.status == "pending",
        or_(Match.ride_1_id.in_([ride_id, candidate_id]), Match.ride_2_id.in_([ride_id, candidate_id])),
    ).first()


def _cancel_live_matches(ride):
    matches = Match.query.filter(
        or_(Match.ride_1_id == ride.ride_id, Match.ride_2_id == ride.ride_id),
        Match.status.in_(["pending", "accepted"]),
    ).all()
    for match in matches:
        if match.status == "accepted":
            partner = match.ride_2 if match.ride_1_id == ride.ride_id else match.ride_1
            if partner.status == "matched":
                partner.status = "waiting"
        match.status = "cancelled"


def register_ride_routes(app):
    @app.get("/dashboard")
    @login_required
    def dashboard():
        ride = get_active_ride()
        return render_template("dashboard.html", ride=ride, current_match=_pending_match_for(ride) if ride else None)

    @app.route("/rides/new", methods=["GET", "POST"])
    @login_required
    def create_ride():
        if get_active_ride():
            flash("Cancel your active ride first.", "warning")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            try:
                ride = _parse_ride_form()
                db.session.add(ride)
                db.session.commit()
                return redirect(url_for("match_results", ride_id=ride.ride_id))
            except (KeyError, ValueError) as error:
                flash(str(error) or "Invalid ride details.", "danger")
        return render_template("create_ride.html")

    @app.get("/rides/<int:ride_id>/matches")
    @login_required
    def match_results(ride_id):
        ride = get_owned_ride(ride_id)
        pending_match = _pending_match_for(ride)
        if pending_match:
            return redirect(url_for("current_match", match_id=pending_match.match_id))
        if ride.status == "waiting":
            results, diagnostics = find_matches(ride, with_diagnostics=True)
        else:
            results, diagnostics = [], {"candidate_count": 0, "excluded": {}}
        return render_template(
            "matches.html", ride=ride, results=results, diagnostics=diagnostics
        )

    @app.post("/rides/<int:ride_id>/matches/<int:candidate_id>")
    @login_required
    def propose_match(ride_id, candidate_id):
        ride = get_owned_ride(ride_id)
        candidate = db.session.get(RideRequest, candidate_id)
        if not candidate or candidate.user_id == session["user_id"]:
            abort(404)
        result = next((item for item in find_matches(ride) if item["ride"].ride_id == candidate_id), None)
        if not result or _candidate_is_busy(ride_id, candidate_id):
            flash("Passenger is no longer available.", "warning")
            return redirect(url_for("match_results", ride_id=ride_id))
        match = Match(ride_1_id=ride_id, ride_2_id=candidate_id,
                      match_probability=result["probability"], **result["stored_features"])
        db.session.add(match)
        db.session.commit()
        return redirect(url_for("current_match", match_id=match.match_id))

    @app.get("/matches/<int:match_id>")
    @login_required
    def current_match(match_id):
        match = get_participant_match(match_id)
        my_ride = match.ride_1 if match.ride_1.user_id == session["user_id"] else match.ride_2
        other_ride = match.ride_2 if my_ride == match.ride_1 else match.ride_1
        return render_template("current_match.html", match=match, my_ride=my_ride, other_ride=other_ride)

    @app.post("/matches/<int:match_id>/accept")
    @login_required
    def accept_match(match_id):
        match = get_participant_match(match_id)
        if match.ride_2.user_id != session["user_id"]:
            abort(403)
        changed_1 = RideRequest.query.filter_by(ride_id=match.ride_1_id, status="waiting").update({"status": "matched"})
        changed_2 = RideRequest.query.filter_by(ride_id=match.ride_2_id, status="waiting").update({"status": "matched"})
        if match.status == "pending" and changed_1 == changed_2 == 1:
            match.status = "accepted"
            Match.query.filter(
                Match.match_id != match.match_id, Match.status == "pending",
                or_(Match.ride_1_id.in_([match.ride_1_id, match.ride_2_id]),
                    Match.ride_2_id.in_([match.ride_1_id, match.ride_2_id])),
            ).update({"status": "cancelled"}, synchronize_session=False)
            db.session.commit()
            flash("Match confirmed!", "success")
        else:
            db.session.rollback()
            flash("Match no longer available.", "warning")
        return redirect(url_for("current_match", match_id=match_id))

    @app.post("/matches/<int:match_id>/reject")
    @login_required
    def reject_match(match_id):
        match = get_participant_match(match_id)
        if match.status == "pending":
            match.status = "rejected"
            db.session.commit()
        return redirect(url_for("dashboard"))

    @app.post("/rides/<int:ride_id>/cancel")
    @login_required
    def cancel_ride(ride_id):
        ride = get_owned_ride(ride_id)
        if ride.status in ("waiting", "matched"):
            _cancel_live_matches(ride)
            ride.status = "cancelled"
            db.session.commit()
        return redirect(url_for("dashboard"))

    @app.get("/history")
    @login_required
    def history():
        rides = (RideRequest.query.filter_by(user_id=session["user_id"])
                 .order_by(RideRequest.created_at.desc()).all())
        return render_template("history.html", rides=rides)
