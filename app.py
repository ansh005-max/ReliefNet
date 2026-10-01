"""ReliefNet backend - Flask + SQLite REST API that also serves the frontend."""
import os, random, sqlite3
from flask import Flask, jsonify, request, g

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "reliefnet.db")
app = Flask(__name__, static_folder="static", static_url_path="")

STATUSES = {"Open", "Team sent", "Evacuating", "Resolved"}
TYPES = {"Flood", "Earthquake", "Fire", "Cyclone", "Landslide"}

# ---------- database ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()

def init_db():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS incidents(id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, loc TEXT, x REAL, y REAL,
        ppl INTEGER, sev TEXT, st TEXT, d TEXT, created TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS shelters(id INTEGER PRIMARY KEY AUTOINCREMENT, n TEXT, a TEXT, cap INTEGER, occ INTEGER, f TEXT, m INTEGER);
    CREATE TABLE IF NOT EXISTS volunteers(id INTEGER PRIMARY KEY AUTOINCREMENT, n TEXT, s TEXT, i INTEGER, created TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS supply_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, shelter_id INTEGER, created TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    """)
    if not c.execute("SELECT 1 FROM incidents").fetchone():
        c.executemany("INSERT INTO incidents(type,loc,x,y,ppl,sev,st,d) VALUES(?,?,?,?,?,?,?,?)", [
            ("Flood", "Riverside Colony", 190, 110, 40, "High", "Open", "Water level above 2 m, families on rooftops."),
            ("Landslide", "North Hill Road", 380, 70, 8, "Medium", "Team sent", "Road blocked, two vehicles stuck."),
            ("Fire", "Old Market", 320, 250, 15, "High", "Open", "Fire spreading in shops, children reported inside."),
            ("Cyclone", "Coastal Village", 480, 200, 60, "Medium", "Evacuating", "Roofs damaged, power out."),
            ("Earthquake", "Sector 9", 120, 250, 5, "Low", "Resolved", "Minor cracks, no injuries.")])
        c.executemany("INSERT INTO shelters(n,a,cap,occ,f,m) VALUES(?,?,?,?,?,?)", [
            ("Govt School Shelter", "Riverside", 200, 140, "Food", 1), ("Community Hall", "Old Market", 120, 60, "Food", 0),
            ("District Stadium", "Sector 9", 500, 180, "Medical", 1), ("Temple Ground", "North Hill", 150, 145, "Food", 0),
            ("Cyclone Centre", "Coastal Village", 300, 90, "Medical", 1)])
        c.executemany("INSERT INTO volunteers(n,s,i) VALUES(?,?,?)", [("Anita", "Medical", 1), ("Rohit", "Rescue", 3)])
    c.commit(); c.close()

def rows(q, *a):
    return [dict(r) for r in db().execute(q, a).fetchall()]

def err(msg, code=400):
    return jsonify(error=msg), code

# ---------- AI logic ----------
KEYWORDS = {"trapped": 20, "injured": 20, "fire": 15, "child": 15, "collapse": 20, "rising": 10, "missing": 15}

def triage(text, people):
    """Score = 2*people + weights of urgent keywords -> High / Medium / Low."""
    score = people * 2 + sum(w for k, w in KEYWORDS.items() if k in text.lower())
    return "High" if score >= 60 else "Medium" if score >= 25 else "Low"

def predict_risk(h, rain, river, seis, wind):
    if h == "Flood":
        r = rain / 300 * 45 + river / 150 * 45 + wind / 200 * 10
    elif h == "Cyclone":
        r = wind / 200 * 60 + rain / 300 * 30 + river / 150 * 10
    else:
        r = seis / 9 * 85 + rain / 300 * 15
    r = round(min(100, max(0, r)))
    lvl = "High" if r >= 65 else "Medium" if r >= 35 else "Low"
    acts = {"High": ["Issue evacuation alert now", "Open all nearby shelters", "Pre-position boats, medics and food"],
            "Medium": ["Send warning SMS to the area", "Check shelter stock", "Put rescue teams on standby"],
            "Low": ["Keep monitoring sensors", "Share safety tips with residents"]}[lvl]
    return {"score": r, "level": lvl, "actions": acts}

def chat_reply(msg):
    m = msg.lower()
    if "how many" in m or "status" in m or "active" in m:
        n = db().execute("SELECT COUNT(*) FROM incidents WHERE st!='Resolved'").fetchone()[0]
        return f"There are {n} active incidents right now. Open the Live map to see them."
    if "shelter" in m:
        s = db().execute("SELECT n, cap-occ AS free FROM shelters ORDER BY free DESC LIMIT 1").fetchone()
        return f"{s['n']} has the most space ({s['free']} beds free). See the Shelters page for all."
    for k, v in [("report", "Use Report to file an emergency. AI triage sets its priority."),
                 ("risk", "The AI risk page scores flood, cyclone or quake risk from readings."),
                 ("volunteer", "Join from the Volunteer page and choose an incident."),
                 ("help", "Call 112 for emergencies, 108 for ambulance, 1078 for NDMA.")]:
        if k in m:
            return v
    return "I can help with shelters, reporting, risk, volunteering, live counts and helplines."

# ---------- routes ----------
@app.get("/")
def home():
    return app.send_static_file("index.html")

@app.get("/api/stats")
def stats():
    d = db()
    q = lambda s: d.execute(s).fetchone()[0]
    return jsonify(active=q("SELECT COUNT(*) FROM incidents WHERE st!='Resolved'"),
                   people=q("SELECT COALESCE(SUM(ppl),0) FROM incidents WHERE st!='Resolved'"),
                   shelters=q("SELECT COUNT(*) FROM shelters"), volunteers=q("SELECT COUNT(*) FROM volunteers"))

@app.get("/api/incidents")
def list_incidents():
    return jsonify(rows("SELECT * FROM incidents ORDER BY id"))

@app.post("/api/incidents")
def add_incident():
    j = request.get_json(silent=True) or {}
    t, loc, desc = j.get("type"), str(j.get("loc", "")).strip(), str(j.get("d", "")).strip()
    try:
        ppl = int(j.get("ppl"))
    except (TypeError, ValueError):
        return err("People affected must be a number")
    if t not in TYPES or not loc or not desc or ppl < 1:
        return err("Type, location, description and people (1+) are required")
    sev = triage(desc, ppl)
    cur = db().execute("INSERT INTO incidents(type,loc,x,y,ppl,sev,st,d) VALUES(?,?,?,?,?,?,?,?)",
                       (t, loc[:80], random.uniform(80, 520), random.uniform(70, 320), ppl, sev, "Open", desc[:500]))
    db().commit()
    return jsonify(rows("SELECT * FROM incidents WHERE id=?", cur.lastrowid)[0]), 201

@app.patch("/api/incidents/<int:i>")
def update_incident(i):
    st = (request.get_json(silent=True) or {}).get("status")
    if st not in STATUSES:
        return err("Invalid status")
    cur = db().execute("UPDATE incidents SET st=? WHERE id=?", (st, i))
    db().commit()
    if not cur.rowcount:
        return err("Incident not found", 404)
    return jsonify(rows("SELECT * FROM incidents WHERE id=?", i)[0])

@app.post("/api/predict")
def predict():
    j = request.get_json(silent=True) or {}
    try:
        v = [float(j.get(k, 0)) for k in ("rain", "river", "seis", "wind")]
    except (TypeError, ValueError):
        return err("Readings must be numbers")
    return jsonify(predict_risk(j.get("hazard", "Flood"), *v))

@app.get("/api/shelters")
def shelters():
    q, f = request.args.get("q", "").lower(), request.args.get("f", "All")
    out = [s for s in rows("SELECT * FROM shelters ORDER BY id")
           if q in (s["n"] + s["a"]).lower() and (f == "All" or s["f"] == f or (f == "Medical" and s["m"]))]
    return jsonify(out)

@app.post("/api/shelters/<int:i>/request")
def supply_request(i):
    if not rows("SELECT 1 FROM shelters WHERE id=?", i):
        return err("Shelter not found", 404)
    db().execute("INSERT INTO supply_requests(shelter_id) VALUES(?)", (i,))
    db().commit()
    return jsonify(ok=True, total=rows("SELECT COUNT(*) c FROM supply_requests WHERE shelter_id=?", i)[0]["c"]), 201

@app.get("/api/volunteers")
def volunteers():
    return jsonify(rows("SELECT * FROM volunteers ORDER BY id"))

@app.post("/api/volunteers")
def add_volunteer():
    j = request.get_json(silent=True) or {}
    n, s = str(j.get("n", "")).strip(), j.get("s")
    try:
        inc = int(j.get("i"))
    except (TypeError, ValueError):
        return err("Choose an incident")
    if not n or not s or not rows("SELECT 1 FROM incidents WHERE id=?", inc):
        return err("Name, skill and a valid incident are required")
    cur = db().execute("INSERT INTO volunteers(n,s,i) VALUES(?,?,?)", (n[:60], s, inc))
    db().commit()
    return jsonify(rows("SELECT * FROM volunteers WHERE id=?", cur.lastrowid)[0]), 201

@app.post("/api/chat")
def chat():
    return jsonify(reply=chat_reply(str((request.get_json(silent=True) or {}).get("message", ""))))

if __name__ == "__main__":
    init_db()
    print("ReliefNet running at http://127.0.0.1:5000")
    app.run(debug=True)
