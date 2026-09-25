# Rickshaw Share — Viva Guide

## 30-second project introduction

> Rickshaw Share is a Flask, SQLite, and machine-learning based web application for matching rickshaw passengers in Bangladesh. A passenger submits pickup, destination, preferred time, and gender preference. The system calculates pickup distance, time difference, route overlap, destination compatibility, and preference compatibility. A regression model estimates detour distance, then a classification model predicts whether the pair is suitable and returns a matching probability. Suitable passengers are ranked by higher probability and lower detour.

## Main objective

The project connects two passengers who:

- start from nearby pickup locations;
- want to travel at similar times;
- have overlapping routes and nearby destinations; and
- satisfy each other's gender preference.

This can reduce individual fare and unnecessary travel while making shared rickshaw journeys easier to arrange.

## Technology stack

| Technology | Purpose | Why it was used |
|---|---|---|
| Python | Backend and machine learning | Supports both web development and ML in one language |
| Flask | Web framework | Lightweight and easy to integrate with saved ML models |
| SQLite | Database | Portable and requires no separate database server |
| SQLAlchemy | ORM | Allows database operations through Python classes |
| pandas | Data processing | Creates model-ready DataFrames and reads the CSV dataset |
| scikit-learn | Machine learning | Trains classification and regression models |
| joblib | Model persistence | Saves and loads trained pipelines as `.pkl` files |
| Leaflet/OpenStreetMap | Map UI | Lets users choose pickup and destination coordinates |
| Waitress | WSGI server | Runs the Flask app reliably on Windows |
| pytest | Automated testing | Verifies matching, authentication, and lifecycle behavior |

## Full application flow

```text
Browser
   |
   v
app.py creates and configures the Flask application
   |
   +--> auth_routes.py handles registration, login, and logout
   |
   +--> ride_routes.py handles rides and match lifecycle
             |
             +--> web_helpers.py checks login and ownership
             +--> models.py reads/writes SQLite records
             +--> matching_engine.py filters and ranks candidates
                           |
                           +--> feature_engineering.py builds model features
                           +--> route_service.py calculates geographic features
                           +--> saved regression model estimates detour
                           +--> saved classifier predicts suitability/probability
```

## File-by-file explanation

### `app.py`

This is the application entry point. `create_app()`:

1. creates the Flask app;
2. configures the secret key and database URL;
3. initializes SQLAlchemy;
4. registers authentication and ride routes;
5. creates the instance directory and database tables; and
6. makes the logged-in user available to every template.

In normal mode, Waitress serves the app at `http://127.0.0.1:5000`. When `FLASK_DEBUG=1`, Flask's development server and auto-reloader are used.

### `database.py`

Creates the shared SQLAlchemy object. It also runs:

```sql
PRAGMA foreign_keys=ON
```

for SQLite connections so invalid foreign-key relationships cannot be stored.

### `models.py`

Defines three database tables:

- `User`: account name, unique email, password hash, gender, and creation time.
- `RideRequest`: pickup, destination, preferred time, preference, and ride status.
- `Match`: the two rides, calculated features, probability, detour, and match status.

Ride status values are `waiting`, `matched`, `completed`, and `cancelled`. Match status values are `pending`, `accepted`, `rejected`, `cancelled`, and `completed`.

### `auth_routes.py`

Handles the home, registration, login, and logout routes. Registration validates required fields, password length, and duplicate emails. Passwords are stored using Werkzeug password hashing, not as plain text. After login, the user's ID is placed in the signed Flask session.

### `web_helpers.py`

Contains reusable security and lookup helpers:

- `login_required()` redirects unauthenticated users to login.
- `get_owned_ride()` prevents one user from opening another user's ride.
- `get_active_ride()` finds the user's latest waiting or matched ride.
- `get_participant_match()` restricts a match page to its two participants.

### `ride_routes.py`

Handles the dashboard, ride creation, match results, proposals, acceptance, rejection, cancellation, and history.

The ride form validates:

- the travel time is in the future;
- latitude is between `-90` and `90`;
- longitude is between `-180` and `180`; and
- pickup and destination names are present.

Only one active ride is allowed per user. During acceptance, conditional database updates ensure both rides are still waiting. This reduces the risk of one ride being accepted by multiple passengers at the same time.

### `feature_engineering.py`

Converts two ride objects into five base features:

1. `pickup_distance_km`
2. `time_difference_min`
3. `route_overlap_percent`
4. `destination_compatibility`
5. `preference_compatible`

Preference compatibility is symmetric: passenger A must accept B, and passenger B must accept A.

### `route_service.py`

Performs offline geographic calculations:

- `haversine_km()` calculates great-circle distance from latitude and longitude.
- `interpolate()` creates 25 sampled points along a direct route.
- `route_overlap_percent()` measures how much the two sampled routes remain within a 700-meter corridor.
- `destination_compatibility()` converts destination distance into a score from `0` to `1`.

The route calculation is a straight-line approximation, not a real road route. A production version could use OSRM or another routing service.

### `matching_engine.py`

The matching engine:

1. loads other rides whose status is `waiting`;
2. excludes the same ride and rides belonging to the same user;
3. builds pair features;
4. rejects preference conflicts;
5. rejects pickup distances over 5 km;
6. rejects time differences over 30 minutes;
7. predicts detour with the regression model;
8. adds detour to the classifier input;
9. predicts suitability and class-1 probability; and
10. sorts results by probability descending, then detour ascending.

The models are loaded lazily and cached in memory. `n_jobs=1` avoids unnecessary process creation for one-row predictions on Windows.

### `train_models.py`

Loads and inspects the dataset, performs exploratory analysis, splits it into 80% training and 20% testing, compares multiple algorithms, and saves the best pipelines.

Classification candidates:

- Logistic Regression
- K-Nearest Neighbors
- Decision Tree
- Random Forest

Regression candidates:

- Linear Regression
- KNN Regressor
- Decision Tree Regressor
- Random Forest Regressor

### `predict.py`

Loads the saved models and demonstrates a prediction for one example passenger pair without running the web application.

### `tests/test_app.py`

Tests good and bad candidates, preference conflicts, ranking, empty results, registration, protected pages, and cancellation of an accepted match. The current suite passes all four tests.

## Matching features and formulas

### Pickup distance

Haversine distance is used because latitude and longitude represent points on the curved surface of Earth. A candidate is removed when the pickup separation exceeds 5 km.

### Time difference

```text
absolute(preferred_time_A - preferred_time_B) / 60 seconds
```

A candidate is removed when the difference exceeds 30 minutes.

### Route overlap

Each direct pickup-to-destination line is sampled at 25 points. A point is considered covered when it lies within 0.7 km of the other route. Coverage in both directions is averaged and converted to a percentage.

### Destination compatibility

```text
max(0, 1 - destination_distance_km / 8)
```

The score is near `1` for close destinations and becomes `0` at 8 km or more.

### Preference compatibility

```text
1 = both passengers accept each other
0 = at least one preference conflicts
```

## Why two ML models are used

The regression model predicts a continuous value: `detour_km`. The classification model predicts a category: suitable (`1`) or not suitable (`0`).

The classifier needs detour as an input, but a new ride does not already have a detour value. Therefore:

```text
Five base features
       |
       v
Regression model predicts detour_km
       |
       v
Six features, including predicted detour
       |
       v
Classifier predicts suitability and probability
```

## Dataset and saved models

The dataset contains:

- 5,000 rows;
- 7 columns;
- no missing values;
- no duplicate rows;
- 3,493 negative matches; and
- 1,507 positive matches.

The saved classifier is a `RandomForestClassifier`. The saved regressor is a `StandardScaler` followed by `LinearRegression`.

Measured performance of the saved models:

| Metric | Value |
|---|---:|
| Classification accuracy | 95.4% |
| Classification precision | 94.7% |
| Classification recall | 89.7% |
| Classification F1 score | 92.15% |
| Classification ROC AUC | 99.17% |
| Regression MAE | 0.935 km |
| Regression RMSE | 1.092 km |
| Regression R-squared | approximately -0.004 |

The classifier is strong on this dataset. The near-zero/negative regression R-squared means the current detour model does not explain detour variation well. Better real road, traffic, and route data would be required for a stronger production detour model.

## Important viva questions and answers

### Is the system AI or rule-based?

It is a hybrid system. Clear business constraints—preference conflict, distance over 5 km, and time over 30 minutes—are rule-based filters. Regression and classification models handle detour estimation and final suitability prediction.

### Why not send every candidate directly to the model?

Hard filters remove clearly invalid candidates, enforce business rules, reduce unnecessary inference, and make the behavior easier to explain.

### Why use Haversine distance?

Latitude and longitude are coordinates on Earth's curved surface. Haversine provides an appropriate great-circle distance approximation, unlike simple Euclidean distance.

### Why use Random Forest?

Relationships among distance, time, overlap, detour, and compatibility can be nonlinear. Random Forest combines multiple decision trees and can model such interactions effectively.

### What is the difference between classification and regression?

Classification predicts a discrete class, such as suitable or not suitable. Regression predicts a continuous value, such as detour distance in kilometers.

### How is match probability calculated?

The classifier's `predict_proba()` method returns the probability of each class. The application takes the probability for class `1`, representing a suitable match.

### Why is regression performed before classification?

`detour_km` is required by the classifier but is not entered by the user. The regression model estimates it from the five base features first.

### Why use a pipeline?

A pipeline keeps preprocessing and the model together, prevents inconsistent transformations, reduces data-leakage risk, and allows the complete process to be saved as one file.

### Why use `random_state=42`?

It makes data splitting and model training reproducible so repeated runs can be compared consistently.

### Why is `stratify=y` used?

It keeps approximately the same positive/negative class ratio in the training and test sets.

### How are passwords protected?

Werkzeug generates a salted password hash. Login checks the submitted password against that hash. Plain passwords are never stored.

### How does the system prevent SQL injection?

It uses SQLAlchemy ORM queries instead of concatenating user input into raw SQL strings.

### Can a passenger create multiple active rides?

No. The application checks for a waiting or matched ride before allowing a new ride.

### Can a passenger match with their own ride?

No. The candidate query excludes the same ride and all rides belonging to the same user. A database constraint also prevents a ride from matching itself.

### How is a race condition handled during acceptance?

Both rides are conditionally updated only if their status is still `waiting`. The match is accepted only when both updates affect exactly one row; otherwise, the transaction is rolled back.

### Why SQLite instead of MySQL or PostgreSQL?

SQLite is portable, requires no separate server, and is suitable for this academic prototype. PostgreSQL would be a better choice for a larger production deployment.

### What are the main limitations?

- Route overlap uses straight-line approximation rather than road routing.
- The dataset is limited and may not represent real passenger behavior.
- The detour regression model needs improvement.
- There is no live GPS, traffic, or real-time notification system.
- Production deployment would need CSRF protection, stronger configuration, monitoring, and a scalable database.

### What future improvements are possible?

- OSRM or another road-routing service
- real traffic and GPS information
- a larger real-world dataset
- improved detour features and regression models
- WebSocket or push notifications
- PostgreSQL and cloud deployment
- stronger security and rate limiting

## Demonstration sequence

1. Register passenger A.
2. Create a ride using the map.
3. Open a private browser window and register passenger B.
4. Create a nearby ride with a similar time and destination.
5. Show the ranked match and probability.
6. Send a match request from passenger A.
7. Accept it as passenger B.
8. Show that both rides are now matched.
9. Cancel one ride and show that the partner becomes waiting again.
10. Open ride history.

## Honest final evaluation

> This is a working academic prototype with a strong classification result. It combines explainable business rules with supervised machine learning. Its main technical limitation is detour regression and straight-line route approximation; real road and traffic data would be the next major improvement.
