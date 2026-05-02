from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import sqlite3
import os
import re
import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "ritlog-geheim-2026"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

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

# ── Database ──────────────────────────────────────────

def init_db():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chauffeurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            werknemersnummer TEXT NOT NULL,
            naam TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trucks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kenteken TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opleggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opleggernummer TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ritten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chauffeur_id INTEGER,
            truck_id INTEGER,
            oplegger_id INTEGER,
            datum TEXT DEFAULT (date('now')),
            starttijd TEXT,
            eindtijd TEXT,
            opmerkingen TEXT,
            pauze_minuten INTEGER DEFAULT 0,
            FOREIGN KEY (chauffeur_id) REFERENCES chauffeurs(id),
            FOREIGN KEY (truck_id) REFERENCES trucks(id),
            FOREIGN KEY (oplegger_id) REFERENCES opleggers(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rit_filialen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rit_id INTEGER,
            filiaalnummer TEXT,
            volgorde INTEGER,
            FOREIGN KEY (rit_id) REFERENCES ritten(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rit_id INTEGER,
            foto_pad TEXT,
            omschrijving TEXT,
            FOREIGN KEY (rit_id) REFERENCES ritten(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filialen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filiaalnummer TEXT UNIQUE NOT NULL,
            straat TEXT,
            huisnummer TEXT,
            postcode TEXT,
            plaats TEXT
        )
    """)

    conn.commit()
    conn.close()

# ── Routes ──────────────────────────────────────────

@app.route("/")
def home():
    return redirect(url_for("overzicht"))

# ── Overzicht ──────────────────────────────────────────
@app.route("/overzicht")
def overzicht():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ritten.id, chauffeurs.naam, trucks.kenteken, opleggers.opleggernummer,
               ritten.datum, ritten.starttijd, ritten.eindtijd, ritten.opmerkingen, ritten.pauze_minuten
        FROM ritten
        LEFT JOIN chauffeurs ON ritten.chauffeur_id = chauffeurs.id
        LEFT JOIN trucks ON ritten.truck_id = trucks.id
        LEFT JOIN opleggers ON ritten.oplegger_id = opleggers.id
        ORDER BY ritten.datum DESC
    """)
    ritten = cursor.fetchall()

    filialen_per_rit = {}
    for rit in ritten:
        cursor.execute("""
            SELECT filiaalnummer FROM rit_filialen
            WHERE rit_id = ? ORDER BY volgorde
        """, (rit[0],))
        filialen_per_rit[rit[0]] = [f[0] for f in cursor.fetchall()]

    vandaag = datetime.date.today()
    van = vandaag.replace(day=1).isoformat()

    cursor.execute("SELECT COUNT(*) FROM ritten WHERE datum >= ?", (van,))
    stats_ritten = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(pauze_minuten), 0) FROM ritten WHERE datum >= ?", (van,))
    stats_pauze = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT rf.filiaalnummer) FROM rit_filialen rf
        JOIN ritten r ON rf.rit_id = r.id WHERE r.datum >= ?
    """, (van,))
    stats_filialen = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(
            (CAST(strftime('%H', eindtijd) AS INTEGER) * 60 + CAST(strftime('%M', eindtijd) AS INTEGER)) -
            (CAST(strftime('%H', starttijd) AS INTEGER) * 60 + CAST(strftime('%M', starttijd) AS INTEGER)) -
            CAST(pauze_minuten AS INTEGER)
        ), 0) FROM ritten WHERE datum >= ? AND starttijd != '' AND eindtijd != ''
    """, (van,))
    minuten = cursor.fetchone()[0]
    stats_uren = round(minuten / 60, 1)

    stats = {
        "ritten": stats_ritten,
        "pauze": stats_pauze,
        "filialen": stats_filialen,
        "uren": stats_uren,
    }

    conn.close()
    return render_template("overzicht.html", ritten=ritten, filialen_per_rit=filialen_per_rit, stats=stats)

# ── Stats API ──────────────────────────────────────────
@app.route("/stats")
def stats():
    periode = request.args.get("periode", "maand")
    vandaag = datetime.date.today()

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

    cursor.execute("SELECT COUNT(*) FROM ritten WHERE datum >= ?", (van,))
    ritten = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(pauze_minuten), 0) FROM ritten WHERE datum >= ?", (van,))
    pauze = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT rf.filiaalnummer) FROM rit_filialen rf
        JOIN ritten r ON rf.rit_id = r.id WHERE r.datum >= ?
    """, (van,))
    filialen = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(
            (CAST(strftime('%H', eindtijd) AS INTEGER) * 60 + CAST(strftime('%M', eindtijd) AS INTEGER)) -
            (CAST(strftime('%H', starttijd) AS INTEGER) * 60 + CAST(strftime('%M', starttijd) AS INTEGER)) -
            CAST(pauze_minuten AS INTEGER)
        ), 0) FROM ritten WHERE datum >= ? AND starttijd != '' AND eindtijd != ''
    """, (van,))
    minuten = cursor.fetchone()[0]
    uren = round(minuten / 60, 1)

    conn.close()
    return jsonify(ritten=ritten, pauze=pauze, filialen=filialen, uren=uren)

# ── Beheer ──────────────────────────────────────────
@app.route("/beheer")
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
    conn.close()
    return render_template("beheer.html", chauffeurs=chauffeurs, trucks=trucks, opleggers=opleggers, filialen=filialen)

# ── Chauffeur toevoegen ──────────────────────────────────────────
@app.route("/chauffeur-toevoegen", methods=["POST"])
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

# ── Truck toevoegen ──────────────────────────────────────────
@app.route("/truck-toevoegen", methods=["POST"])
def truck_toevoegen():
    kenteken = request.form.get("kenteken", "").strip()

    if not valideer_kenteken(kenteken):
        flash("Kenteken is ongeldig. Minimaal 6 tekens, alleen letters, cijfers en koppeltekens.", "fout")
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

# ── Oplegger toevoegen ──────────────────────────────────────────
@app.route("/oplegger-toevoegen", methods=["POST"])
def oplegger_toevoegen():
    opleggernummer = request.form.get("opleggernummer", "").strip()

    if not valideer_opleggernummer(opleggernummer):
        flash("Opleggernummer is ongeldig. Moet beginnen met DD, ED, CDD of CED gevolgd door cijfers (bijv. DD1491).", "fout")
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

# ── Filiaal toevoegen ──────────────────────────────────────────
@app.route("/filiaal-toevoegen", methods=["POST"])
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
        cursor.execute("""
            INSERT INTO filialen (filiaalnummer, straat, huisnummer, postcode, plaats)
            VALUES (?, ?, ?, ?, ?)
        """, (filiaalnummer, straat, huisnummer, postcode, plaats))
        conn.commit()
        flash("Filiaal toegevoegd.", "succes")
    except sqlite3.IntegrityError:
        flash(f"Filiaal {filiaalnummer} bestaat al.", "fout")
    conn.close()
    return redirect(url_for("beheer"))

# ── Rit invoeren ──────────────────────────────────────────
@app.route("/rit")
def rit():
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
    conn.close()
    return render_template("rit.html", chauffeurs=chauffeurs, trucks=trucks, opleggers=opleggers, filialen=filialen)

@app.route("/rit-opslaan", methods=["POST"])
def rit_opslaan():
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

    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ritten (chauffeur_id, truck_id, oplegger_id, datum, starttijd, eindtijd, opmerkingen, pauze_minuten)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (chauffeur_id, truck_id, oplegger_id, datum, starttijd, eindtijd, opmerkingen, pauze_minuten))

    rit_id = cursor.lastrowid

    for volgorde, filiaalnummer in enumerate(filialen):
        if filiaalnummer.strip():
            cursor.execute("""
                INSERT INTO rit_filialen (rit_id, filiaalnummer, volgorde)
                VALUES (?, ?, ?)
            """, (rit_id, filiaalnummer.strip(), volgorde + 1))

    schadefotos = request.files.getlist("schadefoto[]")
    schadeomschrijvingen = request.form.getlist("schadeomschrijving[]")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    for index, foto in enumerate(schadefotos):
        if foto and foto.filename:
            veilige_bestandsnaam = secure_filename(foto.filename)
            opslag_pad = os.path.join(app.config["UPLOAD_FOLDER"], veilige_bestandsnaam)
            foto.save(opslag_pad)
            omschrijving = schadeomschrijvingen[index] if index < len(schadeomschrijvingen) else ""
            cursor.execute("""
                INSERT INTO schades (rit_id, foto_pad, omschrijving)
                VALUES (?, ?, ?)
            """, (rit_id, opslag_pad, omschrijving))

    conn.commit()
    conn.close()
    return redirect(url_for("overzicht"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host='0.0.0.0')
