# Rickshaw Share

An intelligent ride-sharing prototype for rickshaw passengers in Bangladesh. The application combines a Flask web interface, SQLite persistence, route geometry, and trained scikit-learn models to recommend compatible passengers.

## Highlights

- Secure registration, login, and session-based authentication
- Map-assisted pickup and destination selection with Leaflet
- Passenger matching based on location, time, route, and gender preference
- Regression and classification pipelines for detour and suitability prediction
- Complete request, accept, reject, cancel, and ride-history workflow
- SQLite setup on first launch—no manual migration required
- Automated tests for authentication, matching, ranking, and ride lifecycle behavior

## How the application works

```text
Browser request
      |
      v
app.py  -------------------------- creates and configures the Flask app
      |
      +--> auth_routes.py -------- registration, login, logout, and sessions
      |
      +--> ride_routes.py -------- ride creation and match lifecycle
                  |
                  +--> web_helpers.py -------- access and ownership checks
                  +--> models.py ------------ database records
                  +--> matching_engine.py --- filtering, ML inference, ranking
                               |
                               +--> feature_engineering.py -- model-ready features
                               +--> route_service.py ------- distance and overlap
                               +--> models/*.pkl ----------- trained pipelines
```

For a new ride, `ride_routes.py` collects the submitted locations and time. `matching_engine.py` finds eligible waiting rides, asks `feature_engineering.py` and `route_service.py` to calculate the model inputs, runs the saved models, and returns the best candidates in ranked order. Accepted results are persisted through the SQLAlchemy models.

## Project structure

```text
rickshaw-share/
|-- app.py                    # Application factory and entry point
|-- auth_routes.py            # Registration, login, logout, and home routes
|-- ride_routes.py            # Dashboard, rides, and match lifecycle
|-- web_helpers.py            # Authentication and ownership helpers
|-- database.py               # Shared SQLAlchemy extension
|-- models.py                 # User, RideRequest, and Match tables
|-- route_service.py          # Haversine distance and route geometry
|-- feature_engineering.py    # Automatic model feature generation
|-- matching_engine.py        # Candidate filtering, inference, and ranking
|-- train_models.py           # Model training and comparison script
|-- predict.py                # Command-line prediction example
|-- data/                     # Training dataset
|-- models/                   # Saved scikit-learn pipelines
|-- static/                   # CSS and browser-side map code
|-- templates/                # Jinja HTML templates
|-- tests/                    # Automated application and matching tests
|-- instance/                 # Local SQLite data; generated and ignored
|-- requirements.txt          # Python dependencies
`-- .env.example              # Environment-variable reference
```

## User journey

1. A passenger creates an account or signs in.
2. The passenger selects pickup and destination points and a preferred time.
3. The server saves the ride and evaluates other waiting rides.
4. Hard filters remove distant, late, or preference-incompatible candidates.
5. The regression model estimates detour distance.
6. The classifier predicts suitability and matching probability.
7. Candidates are shown from strongest to weakest match.
8. Passengers can request, accept, reject, cancel, or complete a match.

## Database schema

- `users`: ID, name, unique email, Werkzeug password hash, gender, creation time.
- `ride_requests`: user foreign key, pickup/destination names and coordinates, preferred time, gender preference, lifecycle status, creation time.
- `matches`: two ride foreign keys, probability, calculated feature snapshot, estimated detour, lifecycle status, creation time.

Allowed ride statuses are `waiting`, `matched`, `completed`, and `cancelled`. Match statuses are `pending`, `accepted`, `rejected`, `cancelled`, and `completed`. SQLite check constraints and foreign keys preserve the relationships. A conditional database update prevents two requests from accepting the same ride at once.

## Feature and AI flow

No model inputs are typed by the passenger. Pickup separation uses the Haversine great-circle distance. Time difference is the absolute departure-time difference. Route overlap samples both pickup-to-destination lines and measures how much lies in a 700 m shared corridor. Destination compatibility maps destination separation into `0..1`. Preference compatibility requires both passengers' gender preferences to accept the other passenger.

Candidates outside the dataset's trained range (over 5 km pickup separation or 30 minutes apart) and preference conflicts are removed. The existing regression pipeline estimates `detour_km` from its five expected columns. That real model estimate supplies the classifier's required sixth feature. The existing classifier then predicts suitability and `predict_proba()` supplies probability. Suitable candidates are sorted by probability descending, then estimated detour ascending. Pipelines perform their own preprocessing; the application never scales inputs manually.

The geometric route calculation is a documented straight-line approximation suitable for this prototype. Leaflet uses OpenStreetMap tiles, while Nominatim converts map/search selections into coordinates. Production deployments should add a compliant geocoding proxy/cache and may replace direct lines with an OSRM route while retaining the same feature interface.

## Installation

Python 3.10+ is recommended. From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SECRET_KEY = "replace-with-a-long-random-value"
python app.py
```

Open `http://127.0.0.1:5000`. `python app.py` uses the production-ready Waitress server on Windows, so Flask's development-server warning is not shown. Set `FLASK_DEBUG=1` only when you need Flask's development debugger and automatic reload.

## Finding a passenger

On the ride form, search for a place and choose the result whose address is in the correct area. Search results are suggestions; the first result may be a different place with the same name. You can also choose **Choose pickup on map** or **Choose destination on map** and click the map, or use your current location if the browser grants permission. Check the colored pins and selected addresses before creating the ride.

For a match, use two different accounts. Both rides must be waiting; pickup points must be within 5 km, travel times within 30 minutes, and both sharing preferences must accept each other. After the second passenger creates a ride, return to the first passenger's match page and choose **Refresh matches**. If no match appears, that page explains which checks excluded the waiting rides.

The `instance` directory and `rickshaw_share.db` schema initialize automatically on first startup; no retraining or separate migration command is required. To use another database location, set `DATABASE_URL` (for example `sqlite:///C:/path/rickshaw_share.db`).

## Verification

Run automated tests:

```powershell
python -m pytest -q
python predict.py
```

For a manual two-user test, register passenger A in a normal browser and passenger B in a private window. Create nearby rides with similar times and routes. Refresh A's results, send a request, accept it as B, and verify both dashboards show `matched`. Also try distant times/places and conflicting gender preferences; these must not be recommended. Cancel a ride and confirm its match becomes cancelled and appears in history.

The tests cover good geometry, bad/distant pairs, preference conflicts, multiple-candidate ordering, no-candidate behavior, authentication, and protected pages. Existing models are loaded from `models/` when that directory exists, otherwise from the project root.
