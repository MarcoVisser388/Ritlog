from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session, send_from_directory
import sqlite3
import os
import re
import datetime
import bcrypt
import requests
from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DC_ADRES = "Perenmarkt 15, 1681 PG Zwaagdijk-Oost, Nederland"

print("API KEY GELADEN:", GOOGLE_API_KEY)

app = Flask(__name__)
app.secret_key = "ritlog-geheim-2026-xK9mP"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.template_filter('basename')
def basename_filter(path):
    return os.path.basename(path)

# ── Validatie functies ──────────────────────────────────────────

def valideer_opleggernummer(nummer):
    patroon = re.compile(r'^(CDD|CED|DD|ED)\d+$', re.IGNORECASE)
    return bool(patroon.match(nummer.strip()))

def valideer_kenteken(kenteken):
    patroon = re.compile(r'^[A-Za-z0-9\-]{6,}$')
    return bool(patroon.match(kenteken.strip()))

def valideer_postcode(postcode):
    patroon = re.compile(r'^\d{4}\s[A-Za-z]{2}$')
    return bool(patroon.match(postcode.strip()))

def valideer_naam(naam):
    patroon = re.compile(r'^[A-Za-zÀ-ÿ\s\-\.]{2,}$')
    return bool(patroon.match(naam.strip()))

def formatteer_straat(straat):
    return straat.strip().title()

def formatteer_plaats(plaats):
    return plaats.strip().upper()

def formatteer_postcode(postcode):
    postcode = postcode.strip().upper()
    patroon = re.compile(r'^(\d{4})\s*([A-Z]{2})$')
    match = patroon.match(postcode)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return postcode

def formatteer_opleggernummer(nummer):
    return nummer.strip().upper()

def formatteer_kenteken(kenteken):
    return kenteken.strip().upper()

# ── Login decorators ──────────────────────────────────────────

def login_vereist(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "gebruiker_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_vereist(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "gebruiker_id" not in session:
            return redirect(url_for("login"))
        if session.get("rol") != "admin":
            flash("Je hebt geen toegang tot deze pagina.", "fout")
            return redirect(url_for("overzicht"))
        return f(*args, **kwargs)
    return decorated

# ── Kilometerberekening ──────────────────────────────────────────

def bereken_kilometers(filiaalnummers):
    if not filiaalnummers or not GOOGLE_API_KEY:
        print("BEREKEN: geen filialen of geen API key")
        return 0

    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    adressen = []
    for nummer in filiaalnummers:
        cursor.execute("SELECT straat, huisnummer, postcode, plaats FROM filialen WHERE filiaalnummer = ?", (nummer,))
        filiaal = cursor.fetchone()
        if filiaal and filiaal[0] and filiaal[3]:
            adres = f"{filiaal[0]} {filiaal[1]}, {filiaal[2]}, {filiaal[3]}, Nederland"
            adressen.append(adres)
            print("ADRES GEVONDEN:", adres)
        else:
            print("GEEN ADRES VOOR FILIAAL:", nummer)
    conn.close()

    if not adressen:
        print("BEREKEN: geen adressen gevonden")
        return 0

    waypoints = "|".join(adressen)
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": DC_ADRES,
        "destination": DC_ADRES,
        "waypoints": f"optimize:true|{waypoints}",
        "key": GOOGLE_API_KEY,
        "language": "nl",
        "region": "nl"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        print("GOOGLE STATUS:", data.get("status"))
        print("GOOGLE ERROR:", data.get("error_message", "geen"))
        if data.get("status") == "OK":
            totaal_meters = sum(
                leg["distance"]["value"]
                for route in data["routes"]
                for leg in route["legs"]
            )
            km = round(totaal_meters / 1000, 1)
            print("KILOMETERS BEREKEND:", km)
            return km
        return 0
    except Exception as e:
        print("FOUT BIJ API CALL:", e)
        return 0

# ── Database ──────────────────────────────────────────

def init_db():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS gebruikers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gebruikersnaam TEXT NOT NULL UNIQUE,
        wachtwoord TEXT NOT NULL,
        rol TEXT NOT NULL DEFAULT 'chauffeur',
        chauffeur_id INTEGER,
        FOREIGN KEY (chauffeur_id) REFERENCES chauffeurs(id))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS chauffeurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        werknemersnummer TEXT NOT NULL,
        naam TEXT NOT NULL)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS trucks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kenteken TEXT NOT NULL UNIQUE)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS opleggers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opleggernummer TEXT NOT NULL UNIQUE)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS ritten (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chauffeur_id INTEGER,
        truck_id INTEGER,
        oplegger_id INTEGER,
        datum TEXT DEFAULT (date('now')),
        starttijd TEXT,
        eindtijd TEXT,
        opmerkingen TEXT,
        pauze_minuten INTEGER DEFAULT 0,
        is_demo INTEGER DEFAULT 0,
        kilometers REAL DEFAULT 0,
        FOREIGN KEY (chauffeur_id) REFERENCES chauffeurs(id),
        FOREIGN KEY (truck_id) REFERENCES trucks(id),
        FOREIGN KEY (oplegger_id) REFERENCES opleggers(id))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS rit_filialen (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rit_id INTEGER,
        filiaalnummer TEXT,
        volgorde INTEGER,
        FOREIGN KEY (rit_id) REFERENCES ritten(id))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS schades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rit_id INTEGER,
        foto_pad TEXT,
        omschrijving TEXT,
        FOREIGN KEY (rit_id) REFERENCES ritten(id))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS filialen (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filiaalnummer TEXT UNIQUE NOT NULL,
        straat TEXT,
        huisnummer TEXT,
        postcode TEXT,
        plaats TEXT)""")
    try:
        cursor.execute("ALTER TABLE ritten ADD COLUMN is_demo INTEGER DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE ritten ADD COLUMN kilometers REAL DEFAULT 0")
    except:
        pass
    accounts = [
        ("admin", "Mvisser1", "admin", None),
        ("demo", "Ritlog", "demo", None),
        ("jevkovski", "Mvisser1", "chauffeur", None),
    ]
    for gebruikersnaam, wachtwoord, rol, chauffeur_id in accounts:
        cursor.execute("SELECT id FROM gebruikers WHERE gebruikersnaam = ?", (gebruikersnaam,))
        if not cursor.fetchone():
            hash_ww = bcrypt.hashpw(wachtwoord.encode(), bcrypt.gensalt()).decode()
            cursor.execute("INSERT INTO gebruikers (gebruikersnaam, wachtwoord, rol, chauffeur_id) VALUES (?, ?, ?, ?)",
                           (gebruikersnaam, hash_ww, rol, chauffeur_id))
    conn.commit()
    conn.close()

def koppel_jevkovski():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chauffeurs WHERE naam LIKE '%Visser%' OR naam LIKE '%Marco%'")
    chauffeur = cursor.fetchone()
    if chauffeur:
        cursor.execute("UPDATE gebruikers SET chauffeur_id = ? WHERE gebruikersnaam = 'jevkovski'", (chauffeur[0],))
        conn.commit()
    conn.close()

# ── Routes ──────────────────────────────────────────

@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory("uploads", filename)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        gebruikersnaam = request.form.get("gebruikersnaam", "").strip()
        wachtwoord = request.form.get("wachtwoord", "").strip()
        conn = sqlite3.connect("ritten.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gebruikers WHERE gebruikersnaam = ?", (gebruikersnaam,))
        gebruiker = cursor.fetchone()
        conn.close()
        if gebruiker and bcrypt.checkpw(wachtwoord.encode(), gebruiker[2].encode()):
            session["gebruiker_id"] = gebruiker[0]
            session["gebruikersnaam"] = gebruiker[1]
            session["rol"] = gebruiker[3]
            session["chauffeur_id"] = gebruiker[4]
            return redirect(url_for("overzicht"))
        else:
            flash("Gebruikersnaam of wachtwoord klopt niet.", "fout")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def home():
    if "gebruiker_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("overzicht"))

@app.route("/overzicht")
@login_vereist
def overzicht():
    is_demo = session.get("rol") == "demo"
    is_admin = session.get("rol") == "admin"
    chauffeur_id = session.get("chauffeur_id")
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    if is_admin:
        cursor.execute("""SELECT ritten.id, chauffeurs.naam, trucks.kenteken, opleggers.opleggernummer,
               ritten.datum, ritten.starttijd, ritten.eindtijd, ritten.opmerkingen,
               ritten.pauze_minuten, ritten.is_demo, ritten.kilometers
            FROM ritten
            LEFT JOIN chauffeurs ON ritten.chauffeur_id = chauffeurs.id
            LEFT JOIN trucks ON ritten.truck_id = trucks.id
            LEFT JOIN opleggers ON ritten.oplegger_id = opleggers.id
            ORDER BY ritten.datum DESC""")
    elif is_demo:
        cursor.execute("""SELECT ritten.id, chauffeurs.naam, trucks.kenteken, opleggers.opleggernummer,
               ritten.datum, ritten.starttijd, ritten.eindtijd, ritten.opmerkingen,
               ritten.pauze_minuten, ritten.is_demo, ritten.kilometers
            FROM ritten
            LEFT JOIN chauffeurs ON ritten.chauffeur_id = chauffeurs.id
            LEFT JOIN trucks ON ritten.truck_id = trucks.id
            LEFT JOIN opleggers ON ritten.oplegger_id = opleggers.id
            WHERE ritten.is_demo = 1 ORDER BY ritten.datum DESC""")
    else:
        cursor.execute("""SELECT ritten.id, chauffeurs.naam, trucks.kenteken, opleggers.opleggernummer,
               ritten.datum, ritten.starttijd, ritten.eindtijd, ritten.opmerkingen,
               ritten.pauze_minuten, ritten.is_demo, ritten.kilometers
            FROM ritten
            LEFT JOIN chauffeurs ON ritten.chauffeur_id = chauffeurs.id
            LEFT JOIN trucks ON ritten.truck_id = trucks.id
            LEFT JOIN opleggers ON ritten.oplegger_id = opleggers.id
            WHERE ritten.chauffeur_id = ? AND ritten.is_demo = 0
            ORDER BY ritten.datum DESC""", (chauffeur_id,))
    ritten = cursor.fetchall()
    filialen_per_rit = {}
    for rit in ritten:
        cursor.execute("SELECT filiaalnummer FROM rit_filialen WHERE rit_id = ? ORDER BY volgorde", (rit[0],))
        filialen_per_rit[rit[0]] = [f[0] for f in cursor.fetchall()]
    vandaag = datetime.date.today()
    van = vandaag.replace(day=1).isoformat()
    if is_demo:
        cursor.execute("SELECT COUNT(*) FROM ritten WHERE datum >= ? AND is_demo = 1", (van,))
    elif is_admin:
        cursor.execute("SELECT COUNT(*) FROM ritten WHERE datum >= ?", (van,))
    else:
        cursor.execute("SELECT COUNT(*) FROM ritten WHERE datum >= ? AND chauffeur_id = ? AND is_demo = 0", (van, chauffeur_id))
    stats_ritten = cursor.fetchone()[0]
    if is_demo:
        cursor.execute("SELECT COALESCE(SUM(pauze_minuten), 0) FROM ritten WHERE datum >= ? AND is_demo = 1", (van,))
    elif is_admin:
        cursor.execute("SELECT COALESCE(SUM(pauze_minuten), 0) FROM ritten WHERE datum >= ?", (van,))
    else:
        cursor.execute("SELECT COALESCE(SUM(pauze_minuten), 0) FROM ritten WHERE datum >= ? AND chauffeur_id = ? AND is_demo = 0", (van, chauffeur_id))
    stats_pauze = cursor.fetchone()[0]
    if is_demo:
        cursor.execute("SELECT COUNT(DISTINCT rf.filiaalnummer) FROM rit_filialen rf JOIN ritten r ON rf.rit_id = r.id WHERE r.datum >= ? AND r.is_demo = 1", (van,))
    elif is_admin:
        cursor.execute("SELECT COUNT(DISTINCT rf.filiaalnummer) FROM rit_filialen rf JOIN ritten r ON rf.rit_id = r.id WHERE r.datum >= ?", (van,))
    else:
        cursor.execute("SELECT COUNT(DISTINCT rf.filiaalnummer) FROM rit_filialen rf JOIN ritten r ON rf.rit_id = r.id WHERE r.datum >= ? AND r.chauffeur_id = ? AND r.is_demo = 0", (van, chauffeur_id))
    stats_filialen = cursor.fetchone()[0]
    if is_demo:
        cursor.execute("SELECT COALESCE(SUM((CAST(strftime('%H', eindtijd) AS INTEGER) * 60 + CAST(strftime('%M', eindtijd) AS INTEGER)) - (CAST(strftime('%H', starttijd) AS INTEGER) * 60 + CAST(strftime('%M', starttijd) AS INTEGER)) - CAST(pauze_minuten AS INTEGER)), 0) FROM ritten WHERE datum >= ? AND starttijd != '' AND eindtijd != '' AND is_demo = 1", (van,))
    elif is_admin:
        cursor.execute("SELECT COALESCE(SUM((CAST(strftime('%H', eindtijd) AS INTEGER) * 60 + CAST(strftime('%M', eindtijd) AS INTEGER)) - (CAST(strftime('%H', starttijd) AS INTEGER) * 60 + CAST(strftime('%M', starttijd) AS INTEGER)) - CAST(pauze_minuten AS INTEGER)), 0) FROM ritten WHERE datum >= ? AND starttijd != '' AND eindtijd != ''", (van,))
    else:
        cursor.execute("SELECT COALESCE(SUM((CAST(strftime('%H', eindtijd) AS INTEGER) * 60 + CAST(strftime('%M', eindtijd) AS INTEGER)) - (CAST(strftime('%H', starttijd) AS INTEGER) * 60 + CAST(strftime('%M', starttijd) AS INTEGER)) - CAST(pauze_minuten AS INTEGER)), 0) FROM ritten WHERE datum >= ? AND starttijd != '' AND eindtijd != '' AND chauffeur_id = ? AND is_demo = 0", (van, chauffeur_id))
    minuten = cursor.fetchone()[0]
    stats_uren = round(minuten / 60, 1)
    if is_demo:
        cursor.execute("SELECT COALESCE(SUM(kilometers), 0) FROM ritten WHERE datum >= ? AND is_demo = 1", (van,))
    elif is_admin:
        cursor.execute("SELECT COALESCE(SUM(kilometers), 0) FROM ritten WHERE datum >= ?", (van,))
    else:
        cursor.execute("SELECT COALESCE(SUM(kilometers), 0) FROM ritten WHERE datum >= ? AND chauffeur_id = ? AND is_demo = 0", (van, chauffeur_id))
    stats_kilometers = round(cursor.fetchone()[0], 1)
    stats = {"ritten": stats_ritten, "pauze": stats_pauze, "filialen": stats_filialen, "uren": stats_uren, "kilometers": stats_kilometers}
    conn.close()
    return render_template("overzicht.html", ritten=ritten, filialen_per_rit=filialen_per_rit, stats=stats)

@app.route("/stats")
@login_vereist
def stats():
    periode = request.args.get("periode", "maand")
    vandaag = datetime.date.today()
    is_demo = session.get("rol") == "demo"
    is_admin = session.get("rol") == "admin"
    chauffeur_id = session.get("chauffeur_id")
    if periode == "dag":
        van = vandaag.isoformat()
    elif periode == "week":
        van = (vandaag - datetime.timedelta(days=vandaag.weekday())).isoformat()
    elif periode == "maand":
        van = vandaag.replace(day=1).isoformat()
    elif periode == "jaar":
        van = vandaag.replace(month=1, day=1).isoformat()
    else:
        van = "2000-01-01"
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    if is_demo:
        cursor.execute("SELECT COUNT(*) FROM ritten WHERE datum >= ? AND is_demo = 1", (van,))
    elif is_admin:
        cursor.execute("SELECT COUNT(*) FROM ritten WHERE datum >= ?", (van,))
    else:
        cursor.execute("SELECT COUNT(*) FROM ritten WHERE datum >= ? AND chauffeur_id = ? AND is_demo = 0", (van, chauffeur_id))
    ritten = cursor.fetchone()[0]
    if is_demo:
        cursor.execute("SELECT COALESCE(SUM(pauze_minuten), 0) FROM ritten WHERE datum >= ? AND is_demo = 1", (van,))
    elif is_admin:
        cursor.execute("SELECT COALESCE(SUM(pauze_minuten), 0) FROM ritten WHERE datum >= ?", (van,))
    else:
        cursor.execute("SELECT COALESCE(SUM(pauze_minuten), 0) FROM ritten WHERE datum >= ? AND chauffeur_id = ? AND is_demo = 0", (van, chauffeur_id))
    pauze = cursor.fetchone()[0]
    if is_demo:
        cursor.execute("SELECT COUNT(DISTINCT rf.filiaalnummer) FROM rit_filialen rf JOIN ritten r ON rf.rit_id = r.id WHERE r.datum >= ? AND r.is_demo = 1", (van,))
    elif is_admin:
        cursor.execute("SELECT COUNT(DISTINCT rf.filiaalnummer) FROM rit_filialen rf JOIN ritten r ON rf.rit_id = r.id WHERE r.datum >= ?", (van,))
    else:
        cursor.execute("SELECT COUNT(DISTINCT rf.filiaalnummer) FROM rit_filialen rf JOIN ritten r ON rf.rit_id = r.id WHERE r.datum >= ? AND r.chauffeur_id = ? AND r.is_demo = 0", (van, chauffeur_id))
    filialen = cursor.fetchone()[0]
    if is_demo:
        cursor.execute("SELECT COALESCE(SUM((CAST(strftime('%H', eindtijd) AS INTEGER) * 60 + CAST(strftime('%M', eindtijd) AS INTEGER)) - (CAST(strftime('%H', starttijd) AS INTEGER) * 60 + CAST(strftime('%M', starttijd) AS INTEGER)) - CAST(pauze_minuten AS INTEGER)), 0) FROM ritten WHERE datum >= ? AND starttijd != '' AND eindtijd != '' AND is_demo = 1", (van,))
    elif is_admin:
        cursor.execute("SELECT COALESCE(SUM((CAST(strftime('%H', eindtijd) AS INTEGER) * 60 + CAST(strftime('%M', eindtijd) AS INTEGER)) - (CAST(strftime('%H', starttijd) AS INTEGER) * 60 + CAST(strftime('%M', starttijd) AS INTEGER)) - CAST(pauze_minuten AS INTEGER)), 0) FROM ritten WHERE datum >= ? AND starttijd != '' AND eindtijd != ''", (van,))
    else:
        cursor.execute("SELECT COALESCE(SUM((CAST(strftime('%H', eindtijd) AS INTEGER) * 60 + CAST(strftime('%M', eindtijd) AS INTEGER)) - (CAST(strftime('%H', starttijd) AS INTEGER) * 60 + CAST(strftime('%M', starttijd) AS INTEGER)) - CAST(pauze_minuten AS INTEGER)), 0) FROM ritten WHERE datum >= ? AND starttijd != '' AND eindtijd != '' AND chauffeur_id = ? AND is_demo = 0", (van, chauffeur_id))
    minuten = cursor.fetchone()[0]
    uren = round(minuten / 60, 1)
    if is_demo:
        cursor.execute("SELECT COALESCE(SUM(kilometers), 0) FROM ritten WHERE datum >= ? AND is_demo = 1", (van,))
    elif is_admin:
        cursor.execute("SELECT COALESCE(SUM(kilometers), 0) FROM ritten WHERE datum >= ?", (van,))
    else:
        cursor.execute("SELECT COALESCE(SUM(kilometers), 0) FROM ritten WHERE datum >= ? AND chauffeur_id = ? AND is_demo = 0", (van, chauffeur_id))
    kilometers = round(cursor.fetchone()[0], 1)
    conn.close()
    return jsonify(ritten=ritten, pauze=pauze, filialen=filialen, uren=uren, kilometers=kilometers)

@app.route("/beheer")
@admin_vereist
def beheer():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chauffeurs ORDER BY naam")
    chauffeurs = cursor.fetchall()
    cursor.execute("SELECT * FROM trucks ORDER BY kenteken")
    trucks = cursor.fetchall()
    cursor.execute("SELECT * FROM opleggers WHERE opleggernummer != '' ORDER BY opleggernummer")
    opleggers = cursor.fetchall()
    cursor.execute("SELECT * FROM filialen ORDER BY filiaalnummer")
    filialen = cursor.fetchall()
    cursor.execute("SELECT g.id, g.gebruikersnaam, g.rol, c.naam FROM gebruikers g LEFT JOIN chauffeurs c ON g.chauffeur_id = c.id ORDER BY g.rol")
    gebruikers = cursor.fetchall()
    conn.close()
    return render_template("beheer.html", chauffeurs=chauffeurs, trucks=trucks, opleggers=opleggers, filialen=filialen, gebruikers=gebruikers)

@app.route("/chauffeur-toevoegen", methods=["POST"])
@admin_vereist
def chauffeur_toevoegen():
    werknemersnummer = request.form.get("werknemersnummer", "").strip()
    naam = request.form.get("naam", "").strip()
    fouten = []
    if not werknemersnummer.isdigit():
        fouten.append("Werknemersnummer mag alleen cijfers bevatten.")
    if not valideer_naam(naam):
        fouten.append("Naam is ongeldig. Gebruik alleen letters.")
    if fouten:
        for fout in fouten:
            flash(fout, "fout")
        return redirect(url_for("beheer"))
    naam = naam.title()
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chauffeurs (werknemersnummer, naam) VALUES (?, ?)", (werknemersnummer, naam))
    conn.commit()
    conn.close()
    flash("Chauffeur toegevoegd.", "succes")
    return redirect(url_for("beheer"))

@app.route("/truck-toevoegen", methods=["POST"])
@admin_vereist
def truck_toevoegen():
    kenteken = request.form.get("kenteken", "").strip()
    if not valideer_kenteken(kenteken):
        flash("Kenteken is ongeldig.", "fout")
        return redirect(url_for("beheer"))
    kenteken = formatteer_kenteken(kenteken)
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO trucks (kenteken) VALUES (?)", (kenteken,))
        conn.commit()
        flash("Truck toegevoegd.", "succes")
    except sqlite3.IntegrityError:
        flash(f"Kenteken {kenteken} bestaat al.", "fout")
    conn.close()
    return redirect(url_for("beheer"))

@app.route("/oplegger-toevoegen", methods=["POST"])
@admin_vereist
def oplegger_toevoegen():
    opleggernummer = request.form.get("opleggernummer", "").strip()
    if not valideer_opleggernummer(opleggernummer):
        flash("Opleggernummer is ongeldig. Moet beginnen met DD, ED, CDD of CED gevolgd door cijfers.", "fout")
        return redirect(url_for("beheer"))
    opleggernummer = formatteer_opleggernummer(opleggernummer)
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO opleggers (opleggernummer) VALUES (?)", (opleggernummer,))
        conn.commit()
        flash("Oplegger toegevoegd.", "succes")
    except sqlite3.IntegrityError:
        flash(f"Opleggernummer {opleggernummer} bestaat al.", "fout")
    conn.close()
    return redirect(url_for("beheer"))

@app.route("/filiaal-toevoegen", methods=["POST"])
@admin_vereist
def filiaal_toevoegen():
    filiaalnummer = request.form.get("filiaalnummer", "").strip()
    straat = request.form.get("straat", "").strip()
    huisnummer = request.form.get("huisnummer", "").strip()
    postcode = request.form.get("postcode", "").strip()
    plaats = request.form.get("plaats", "").strip()
    fouten = []
    if not filiaalnummer.isdigit() or len(filiaalnummer) != 4:
        fouten.append("Filiaalnummer moet precies 4 cijfers zijn.")
    if postcode and not valideer_postcode(postcode):
        fouten.append("Postcode is ongeldig. Gebruik formaat: 1234 AB.")
    if fouten:
        for fout in fouten:
            flash(fout, "fout")
        return redirect(url_for("beheer"))
    straat = formatteer_straat(straat) if straat else ""
    plaats = formatteer_plaats(plaats) if plaats else ""
    postcode = formatteer_postcode(postcode) if postcode else ""
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO filialen (filiaalnummer, straat, huisnummer, postcode, plaats) VALUES (?, ?, ?, ?, ?)", (filiaalnummer, straat, huisnummer, postcode, plaats))
        conn.commit()
        flash("Filiaal toegevoegd.", "succes")
    except sqlite3.IntegrityError:
        flash(f"Filiaal {filiaalnummer} bestaat al.", "fout")
    conn.close()
    return redirect(url_for("beheer"))

@app.route("/gebruiker-toevoegen", methods=["POST"])
@admin_vereist
def gebruiker_toevoegen():
    gebruikersnaam = request.form.get("gebruikersnaam", "").strip()
    wachtwoord = request.form.get("wachtwoord", "").strip()
    rol = request.form.get("rol", "chauffeur").strip()
    chauffeur_id = request.form.get("chauffeur_id", None)
    if not gebruikersnaam or not wachtwoord:
        flash("Gebruikersnaam en wachtwoord zijn verplicht.", "fout")
        return redirect(url_for("beheer"))
    if chauffeur_id == "":
        chauffeur_id = None
    hash_ww = bcrypt.hashpw(wachtwoord.encode(), bcrypt.gensalt()).decode()
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO gebruikers (gebruikersnaam, wachtwoord, rol, chauffeur_id) VALUES (?, ?, ?, ?)", (gebruikersnaam, hash_ww, rol, chauffeur_id))
        conn.commit()
        flash("Gebruiker toegevoegd.", "succes")
    except sqlite3.IntegrityError:
        flash(f"Gebruikersnaam {gebruikersnaam} bestaat al.", "fout")
    conn.close()
    return redirect(url_for("beheer"))

@app.route("/demo-wissen", methods=["POST"])
@admin_vereist
def demo_wissen():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM ritten WHERE is_demo = 1")
    demo_ritten = [r[0] for r in cursor.fetchall()]
    for rit_id in demo_ritten:
        cursor.execute("DELETE FROM rit_filialen WHERE rit_id = ?", (rit_id,))
        cursor.execute("DELETE FROM schades WHERE rit_id = ?", (rit_id,))
    cursor.execute("DELETE FROM ritten WHERE is_demo = 1")
    conn.commit()
    conn.close()
    flash("Alle demo ritten zijn verwijderd.", "succes")
    return redirect(url_for("beheer"))

@app.route("/rit")
@login_vereist
def rit():
    is_demo = session.get("rol") == "demo"
    is_admin = session.get("rol") == "admin"
    chauffeur_id = session.get("chauffeur_id")
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    if is_admin:
        cursor.execute("SELECT * FROM chauffeurs ORDER BY naam")
    elif is_demo:
        cursor.execute("SELECT * FROM chauffeurs WHERE naam = 'Demo Chauffeur'")
    else:
        cursor.execute("SELECT * FROM chauffeurs WHERE id = ?", (chauffeur_id,))
    chauffeurs = cursor.fetchall()
    cursor.execute("SELECT * FROM trucks ORDER BY kenteken")
    trucks = cursor.fetchall()
    cursor.execute("SELECT * FROM opleggers WHERE opleggernummer != '' ORDER BY opleggernummer")
    opleggers = cursor.fetchall()
    cursor.execute("SELECT * FROM filialen ORDER BY filiaalnummer")
    filialen = cursor.fetchall()
    conn.close()
    return render_template("rit.html", chauffeurs=chauffeurs, trucks=trucks, opleggers=opleggers, filialen=filialen)

@app.route("/rit-opslaan", methods=["POST"])
@login_vereist
def rit_opslaan():
    is_demo = session.get("rol") == "demo"
    chauffeur_id = request.form.get("chauffeur_id", "").strip()
    truck_id = request.form.get("truck_id", "").strip()
    oplegger_id = request.form.get("oplegger_id", "").strip()
    datum = request.form.get("datum", "").strip()
    starttijd = request.form.get("starttijd", "").strip()
    eindtijd = request.form.get("eindtijd", "").strip()
    opmerkingen = request.form.get("opmerkingen", "").strip()
    pauze_minuten = request.form.get("pauze_minuten", 0)
    filialen = request.form.getlist("filiaal[]")
    try:
        chauffeur_id = int(chauffeur_id)
        truck_id = int(truck_id)
        oplegger_id = int(oplegger_id)
        pauze_minuten = int(pauze_minuten)
    except (ValueError, TypeError):
        flash("Ongeldige invoer gedetecteerd.", "fout")
        return redirect(url_for("rit"))
    filialen_gefilterd = [f for f in filialen if f.strip()]
    kilometers = bereken_kilometers(filialen_gefilterd)
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO ritten (chauffeur_id, truck_id, oplegger_id, datum, starttijd, eindtijd, opmerkingen, pauze_minuten, is_demo, kilometers)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (chauffeur_id, truck_id, oplegger_id, datum, starttijd, eindtijd, opmerkingen, pauze_minuten, 1 if is_demo else 0, kilometers))
    rit_id = cursor.lastrowid
    for volgorde, filiaalnummer in enumerate(filialen_gefilterd):
        cursor.execute("INSERT INTO rit_filialen (rit_id, filiaalnummer, volgorde) VALUES (?, ?, ?)", (rit_id, filiaalnummer, volgorde + 1))
    schadefotos = request.files.getlist("schadefoto[]")
    schadeomschrijvingen = request.form.getlist("schadeomschrijving[]")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    for index, foto in enumerate(schadefotos):
        if foto and foto.filename:
            veilige_bestandsnaam = secure_filename(foto.filename)
            opslag_pad = os.path.join(app.config["UPLOAD_FOLDER"], veilige_bestandsnaam)
            foto.save(opslag_pad)
            omschrijving = schadeomschrijvingen[index] if index < len(schadeomschrijvingen) else ""
            cursor.execute("INSERT INTO schades (rit_id, foto_pad, omschrijving) VALUES (?, ?, ?)", (rit_id, opslag_pad, omschrijving))
    conn.commit()
    conn.close()
    return redirect(url_for("overzicht"))

@app.route("/rit-detail/<int:rit_id>")
@login_vereist
def rit_detail(rit_id):
    is_admin = session.get("rol") == "admin"
    is_demo = session.get("rol") == "demo"
    chauffeur_id = session.get("chauffeur_id")
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("""SELECT ritten.id, ritten.chauffeur_id, ritten.truck_id, ritten.oplegger_id,
               ritten.datum, ritten.starttijd, ritten.eindtijd, ritten.opmerkingen,
               ritten.pauze_minuten, ritten.is_demo, ritten.kilometers FROM ritten WHERE id = ?""", (rit_id,))
    rit = cursor.fetchone()
    if not rit:
        flash("Rit niet gevonden.", "fout")
        conn.close()
        return redirect(url_for("overzicht"))
    if is_demo and rit[9] != 1:
        flash("Geen toegang.", "fout")
        conn.close()
        return redirect(url_for("overzicht"))
    if not is_admin and not is_demo and rit[1] != chauffeur_id:
        flash("Je kunt alleen je eigen ritten bekijken.", "fout")
        conn.close()
        return redirect(url_for("overzicht"))
    cursor.execute("SELECT naam FROM chauffeurs WHERE id = ?", (rit[1],))
    chauffeur = cursor.fetchone()
    chauffeur_naam = chauffeur[0] if chauffeur else "Onbekend"
    cursor.execute("SELECT kenteken FROM trucks WHERE id = ?", (rit[2],))
    truck = cursor.fetchone()
    truck_kenteken = truck[0] if truck else "Onbekend"
    cursor.execute("SELECT opleggernummer FROM opleggers WHERE id = ?", (rit[3],))
    oplegger = cursor.fetchone()
    oplegger_nummer = oplegger[0] if oplegger else "Onbekend"
    cursor.execute("""SELECT rf.filiaalnummer, f.straat, f.huisnummer, f.postcode, f.plaats
        FROM rit_filialen rf LEFT JOIN filialen f ON rf.filiaalnummer = f.filiaalnummer
        WHERE rf.rit_id = ? ORDER BY rf.volgorde""", (rit_id,))
    filialen_rows = cursor.fetchall()
    filialen = [{"filiaalnummer": r[0], "straat": r[1], "huisnummer": r[2], "postcode": r[3], "plaats": r[4]} for r in filialen_rows]
    cursor.execute("SELECT foto_pad, omschrijving FROM schades WHERE rit_id = ?", (rit_id,))
    schades_rows = cursor.fetchall()
    schades = [{"foto_pad": r[0], "omschrijving": r[1]} for r in schades_rows]
    gewerkte_uren = None
    if rit[5] and rit[6]:
        start = rit[5].split(":")
        eind = rit[6].split(":")
        minuten = (int(eind[0]) * 60 + int(eind[1])) - (int(start[0]) * 60 + int(start[1])) - (rit[8] or 0)
        gewerkte_uren = round(minuten / 60, 1)
    conn.close()
    return render_template("rit_detail.html", rit=rit, chauffeur_naam=chauffeur_naam,
                           truck_kenteken=truck_kenteken, oplegger_nummer=oplegger_nummer,
                           filialen=filialen, schades=schades, gewerkte_uren=gewerkte_uren)

@app.route("/rit-verwijderen/<int:rit_id>", methods=["POST"])
@admin_vereist
def rit_verwijderen(rit_id):
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM ritten WHERE id = ?", (rit_id,))
    rit = cursor.fetchone()
    if not rit:
        flash("Rit niet gevonden.", "fout")
        conn.close()
        return redirect(url_for("overzicht"))
    cursor.execute("DELETE FROM rit_filialen WHERE rit_id = ?", (rit_id,))
    cursor.execute("DELETE FROM schades WHERE rit_id = ?", (rit_id,))
    cursor.execute("DELETE FROM ritten WHERE id = ?", (rit_id,))
    conn.commit()
    conn.close()
    flash("Rit verwijderd.", "succes")
    return redirect(url_for("overzicht"))

@app.route("/rit-bewerken/<int:rit_id>")
@login_vereist
def rit_bewerken(rit_id):
    is_admin = session.get("rol") == "admin"
    chauffeur_id = session.get("chauffeur_id")
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("""SELECT ritten.id, ritten.chauffeur_id, ritten.truck_id, ritten.oplegger_id,
               ritten.datum, ritten.starttijd, ritten.eindtijd, ritten.opmerkingen,
               ritten.pauze_minuten FROM ritten WHERE id = ?""", (rit_id,))
    rit = cursor.fetchone()
    if not rit:
        flash("Rit niet gevonden.", "fout")
        conn.close()
        return redirect(url_for("overzicht"))
    if not is_admin and rit[1] != chauffeur_id:
        flash("Je kunt alleen je eigen ritten bewerken.", "fout")
        conn.close()
        return redirect(url_for("overzicht"))
    cursor.execute("SELECT filiaalnummer FROM rit_filialen WHERE rit_id = ? ORDER BY volgorde", (rit_id,))
    huidige_filialen = [f[0] for f in cursor.fetchall()]
    cursor.execute("SELECT * FROM chauffeurs ORDER BY naam")
    chauffeurs = cursor.fetchall()
    cursor.execute("SELECT * FROM trucks ORDER BY kenteken")
    trucks = cursor.fetchall()
    cursor.execute("SELECT * FROM opleggers WHERE opleggernummer != '' ORDER BY opleggernummer")
    opleggers = cursor.fetchall()
    cursor.execute("SELECT * FROM filialen ORDER BY filiaalnummer")
    filialen = cursor.fetchall()
    conn.close()
    return render_template("rit_bewerken.html", rit=rit, huidige_filialen=huidige_filialen,
                           chauffeurs=chauffeurs, trucks=trucks, opleggers=opleggers, filialen=filialen)

@app.route("/rit-bewerken-opslaan/<int:rit_id>", methods=["POST"])
@login_vereist
def rit_bewerken_opslaan(rit_id):
    is_admin = session.get("rol") == "admin"
    chauffeur_id = session.get("chauffeur_id")
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("SELECT chauffeur_id FROM ritten WHERE id = ?", (rit_id,))
    rit = cursor.fetchone()
    if not rit or (not is_admin and rit[0] != chauffeur_id):
        flash("Geen toegang.", "fout")
        conn.close()
        return redirect(url_for("overzicht"))
    truck_id = request.form.get("truck_id", "").strip()
    oplegger_id = request.form.get("oplegger_id", "").strip()
    datum = request.form.get("datum", "").strip()
    starttijd = request.form.get("starttijd", "").strip()
    eindtijd = request.form.get("eindtijd", "").strip()
    opmerkingen = request.form.get("opmerkingen", "").strip()
    pauze_minuten = request.form.get("pauze_minuten", 0)
    filialen = request.form.getlist("filiaal[]")
    try:
        truck_id = int(truck_id)
        oplegger_id = int(oplegger_id)
        pauze_minuten = int(pauze_minuten)
    except (ValueError, TypeError):
        flash("Ongeldige invoer.", "fout")
        conn.close()
        return redirect(url_for("rit_bewerken", rit_id=rit_id))
    filialen_gefilterd = [f for f in filialen if f.strip()]
    kilometers = bereken_kilometers(filialen_gefilterd)
    cursor.execute("""UPDATE ritten SET truck_id=?, oplegger_id=?, datum=?, starttijd=?, eindtijd=?,
                          opmerkingen=?, pauze_minuten=?, kilometers=? WHERE id=?""",
                   (truck_id, oplegger_id, datum, starttijd, eindtijd, opmerkingen, pauze_minuten, kilometers, rit_id))
    cursor.execute("DELETE FROM rit_filialen WHERE rit_id = ?", (rit_id,))
    for volgorde, filiaalnummer in enumerate(filialen_gefilterd):
        cursor.execute("INSERT INTO rit_filialen (rit_id, filiaalnummer, volgorde) VALUES (?, ?, ?)",
                       (rit_id, filiaalnummer, volgorde + 1))
    conn.commit()
    conn.close()
    flash("Rit bijgewerkt.", "succes")
    return redirect(url_for("overzicht"))

@app.route("/api/ritten")
def api_ritten():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ritten.id, chauffeurs.naam, trucks.kenteken, opleggers.opleggernummer,
               ritten.datum, ritten.starttijd, ritten.eindtijd, ritten.pauze_minuten,
               ritten.kilometers, ritten.opmerkingen
        FROM ritten
        LEFT JOIN chauffeurs ON ritten.chauffeur_id = chauffeurs.id
        LEFT JOIN trucks ON ritten.truck_id = trucks.id
        LEFT JOIN opleggers ON ritten.oplegger_id = opleggers.id
        WHERE ritten.is_demo = 0
        ORDER BY ritten.datum DESC
    """)
    ritten = cursor.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "chauffeur": r[1], "truck": r[2], "oplegger": r[3],
                     "datum": r[4], "starttijd": r[5], "eindtijd": r[6],
                     "pauze_minuten": r[7], "kilometers": r[8], "opmerkingen": r[9]} for r in ritten])

@app.route("/api/filialen")
def api_filialen():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, filiaalnummer, straat, huisnummer, postcode, plaats FROM filialen ORDER BY filiaalnummer")
    filialen = cursor.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "filiaalnummer": r[1], "straat": r[2],
                     "huisnummer": r[3], "postcode": r[4], "plaats": r[5]} for r in filialen])

@app.route("/api/chauffeurs")
def api_chauffeurs():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, werknemersnummer, naam FROM chauffeurs ORDER BY naam")
    chauffeurs = cursor.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "werknemersnummer": r[1], "naam": r[2]} for r in chauffeurs])

@app.route("/api/trucks")
def api_trucks():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, kenteken FROM trucks ORDER BY kenteken")
    trucks = cursor.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "kenteken": r[1]} for r in trucks])

@app.route("/api/opleggers")
def api_opleggers():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, opleggernummer FROM opleggers ORDER BY opleggernummer")
    opleggers = cursor.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "opleggernummer": r[1]} for r in opleggers])

@app.route("/api/rit-filialen")
def api_rit_filialen():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rf.rit_id, rf.filiaalnummer, rf.volgorde
        FROM rit_filialen rf
        JOIN ritten r ON rf.rit_id = r.id
        WHERE r.is_demo = 0
        ORDER BY rf.rit_id, rf.volgorde
    """)
    rit_filialen = cursor.fetchall()
    conn.close()
    return jsonify([{"rit_id": r[0], "filiaalnummer": r[1], "volgorde": r[2]} for r in rit_filialen])

if __name__ == "__main__":
    init_db()
    koppel_jevkovski()
    app.run(debug=True, host='0.0.0.0')