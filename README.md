# ReliefNet - AI Disaster Response & Relief Management System
College mini project: HTML/CSS/JS frontend + Flask (Python) REST API + SQLite database.

## Run
1. Install Python 3.9+
2. `pip install -r requirements.txt`
3. `python app.py`
4. Open http://127.0.0.1:5000

The database (`reliefnet.db`) is created and seeded automatically on first run. Delete it to reset.

## Structure
- app.py - Flask server, REST API, SQLite, AI triage + risk logic, chatbot
- static/index.html, static/css/style.css, static/js/app.js - frontend (served by Flask)

## API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/stats | Dashboard counters |
| GET/POST | /api/incidents | List / report incident (AI triage sets priority) |
| PATCH | /api/incidents/<id> | Update status (Open, Team sent, Evacuating, Resolved) |
| POST | /api/predict | AI risk score from rainfall, river, seismic, wind |
| GET | /api/shelters?q=&f= | Search / filter shelters |
| POST | /api/shelters/<id>/request | Request supplies |
| GET/POST | /api/volunteers | List / register volunteer |
| POST | /api/chat | Assistant chatbot (uses live DB data) |

## Features
Live map (auto-refresh), AI triage, AI risk predictor, shelter finder, volunteer assignment, emergency contacts, chatbot, dark mode.
