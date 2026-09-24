from datetime import datetime,timedelta
import pytest
from app import create_app
from database import db
from feature_engineering import build_pair_features
from matching_engine import find_matches
from models import Match,RideRequest,User
from werkzeug.security import generate_password_hash

@pytest.fixture()
def app():
    app=create_app({"TESTING":True,"SECRET_KEY":"test","SQLALCHEMY_DATABASE_URI":"sqlite:///:memory:"})
    with app.app_context(): db.create_all(); yield app; db.drop_all()

def user(name,gender="female"):
    u=User(name=name,email=f"{name.lower()}@test.com",password_hash=generate_password_hash("password"),gender=gender); db.session.add(u); db.session.flush(); return u

def ride(u,pickup,dest,minutes=0,pref="any"):
    r=RideRequest(user_id=u.user_id,pickup_name="Pickup",pickup_latitude=pickup[0],pickup_longitude=pickup[1],destination_name="Destination",destination_latitude=dest[0],destination_longitude=dest[1],preferred_time=datetime.now()+timedelta(hours=1,minutes=minutes),gender_preference=pref); db.session.add(r); db.session.flush(); return r

def test_good_bad_preference_and_multiple_candidates(app):
    with app.app_context():
        a=ride(user("A"),(23.8103,90.4125),(23.7509,90.3932))
        b=ride(user("B"),(23.8110,90.4130),(23.7520,90.3940),3)
        bad=ride(user("Far"),(23.45,90.10),(23.50,90.15),90)
        conflict=ride(user("Conflict","male"),(23.8108,90.4128),(23.751,90.393),2,"male")
        db.session.commit(); good=build_pair_features(a,b); poor=build_pair_features(a,bad); clash=build_pair_features(a,conflict)
        assert good["pickup_distance_km"]<.2 and good["route_overlap_percent"]>80
        assert poor["pickup_distance_km"]>5 and poor["time_difference_min"]>30
        assert clash["preference_compatible"]==0
        results=find_matches(a); assert all(x["features"]["preference_compatible"] for x in results)
        assert results==sorted(results,key=lambda x:(-x["probability"],x["estimated_detour_km"]))

def test_no_available_match(app):
    with app.app_context():
        a=ride(user("Solo"),(23.81,90.41),(23.75,90.39)); db.session.commit(); assert find_matches(a)==[]

def test_registration_and_protected_dashboard(app):
    client=app.test_client(); assert client.get('/dashboard').status_code==302
    response=client.post('/register',data={"name":"Nila","email":"nila@test.com","password":"secure123","gender":"female"},follow_redirects=True)
    assert response.status_code==200 and b"Hello, Nila" in response.data

def test_cancel_confirmed_match_releases_partner(app):
    with app.app_context():
        a=ride(user("Owner"),(23.81,90.41),(23.75,90.39)); b=ride(user("Partner"),(23.811,90.411),(23.751,90.391),2)
        a.status=b.status="matched"; m=Match(ride_1_id=a.ride_id,ride_2_id=b.ride_id,match_probability=.9,pickup_distance_km=.1,time_difference_min=2,route_overlap_percent=95,destination_compatibility=.98,estimated_detour_km=.3,status="accepted"); db.session.add(m); db.session.commit(); owner_id=a.user_id; aid=a.ride_id; bid=b.ride_id; mid=m.match_id
    client=app.test_client()
    with client.session_transaction() as s: s["user_id"]=owner_id
    assert client.post(f"/rides/{aid}/cancel").status_code==302
    with app.app_context(): assert db.session.get(RideRequest,aid).status=="cancelled" and db.session.get(RideRequest,bid).status=="waiting" and db.session.get(Match,mid).status=="cancelled"
