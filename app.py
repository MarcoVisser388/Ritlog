from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

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
            kenteken TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opleggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opleggernummer TEXT NOT NULL
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

@app.route("/")
def home():
    return redirect(url_for("beheer"))

# ── Beheer ──────────────────────────────────────────
@app.route("/beheer")
def beheer():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chauffeurs")
    chauffeurs = cursor.fetchall()
    cursor.execute("SELECT * FROM trucks")
    trucks = cursor.fetchall()
    cursor.execute("SELECT * FROM opleggers")
    opleggers = cursor.fetchall()
    cursor.execute("SELECT * FROM filialen ORDER BY filiaalnummer")
    filialen = cursor.fetchall()
    conn.close()
    return render_template("beheer.html", chauffeurs=chauffeurs, trucks=trucks, opleggers=opleggers, filialen=filialen)

@app.route("/chauffeur-toevoegen", methods=["POST"])
def chauffeur_toevoegen():
    werknemersnummer = request.form["werknemersnummer"]
    naam = request.form["naam"]
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chauffeurs (werknemersnummer, naam) VALUES (?, ?)", (werknemersnummer, naam))
    conn.commit()
    conn.close()
    return redirect(url_for("beheer"))

@app.route("/truck-toevoegen", methods=["POST"])
def truck_toevoegen():
    kenteken = request.form["kenteken"]
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO trucks (kenteken) VALUES (?)", (kenteken,))
    conn.commit()
    conn.close()
    return redirect(url_for("beheer"))

@app.route("/oplegger-toevoegen", methods=["POST"])
def oplegger_toevoegen():
    opleggernummer = request.form["opleggernummer"]
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO opleggers (opleggernummer) VALUES (?)", (opleggernummer,))
    conn.commit()
    conn.close()
    return redirect(url_for("beheer"))

@app.route("/filiaal-toevoegen", methods=["POST"])
def filiaal_toevoegen():
    filiaalnummer = request.form["filiaalnummer"]
    straat = request.form["straat"]
    huisnummer = request.form["huisnummer"]
    postcode = request.form["postcode"]
    plaats = request.form["plaats"]

    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO filialen (filiaalnummer, straat, huisnummer, postcode, plaats)
            VALUES (?, ?, ?, ?, ?)
        """, (filiaalnummer, straat, huisnummer, postcode, plaats))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return redirect(url_for("beheer"))

@app.route("/rit")
def rit():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM chauffeurs")
    chauffeurs = cursor.fetchall()

    cursor.execute("SELECT * FROM trucks")
    trucks = cursor.fetchall()

    cursor.execute("SELECT * FROM opleggers")
    opleggers = cursor.fetchall()

    cursor.execute("SELECT * FROM filialen ORDER BY filiaalnummer")
    filialen = cursor.fetchall()

    conn.close()

    return render_template(
        "rit.html",
        chauffeurs=chauffeurs,
        trucks=trucks,
        opleggers=opleggers,
        filialen=filialen
    )

@app.route("/rit-opslaan", methods=["POST"])
def rit_opslaan():
    chauffeur_id = request.form["chauffeur_id"]
    truck_id = request.form["truck_id"]
    oplegger_id = request.form["oplegger_id"]
    datum = request.form["datum"]
    starttijd = request.form["starttijd"]
    eindtijd = request.form["eindtijd"]
    opmerkingen = request.form["opmerkingen"]
    pauze_minuten = request.form.get("pauze_minuten", 0)
    filialen = request.form.getlist("filiaal[]")

    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO ritten (chauffeur_id, truck_id, oplegger_id, datum, starttijd, eindtijd, opmerkingen,
                         pauze_minuten)
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

    for index, foto in enumerate(schadefotos):
        if foto and foto.filename:
            veilige_bestandsnaam = secure_filename(foto.filename)
            opslag_pad = os.path.join(app.config["UPLOAD_FOLDER"], veilige_bestandsnaam)
            foto.save(opslag_pad)

            omschrijving = ""

            if index < len(schadeomschrijvingen):
                omschrijving = schadeomschrijvingen[index]

            cursor.execute("""
                INSERT INTO schades (rit_id, foto_pad, omschrijving)
                VALUES (?, ?, ?)
            """, (rit_id, opslag_pad, omschrijving))

    conn.commit()
    conn.close()

    return redirect(url_for("overzicht"))

@app.route("/overzicht")
def overzicht():
    conn = sqlite3.connect("ritten.db")
    cursor = conn.cursor()
    cursor.execute("""
                   SELECT ritten.id,
                          chauffeurs.naam,
                          trucks.kenteken,
                          opleggers.opleggernummer,
                          ritten.datum,
                          ritten.starttijd,
                          ritten.eindtijd,
                          ritten.opmerkingen,
                          ritten.pauze_minuten
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

    conn.close()
    return render_template("overzicht.html", ritten=ritten, filialen_per_rit=filialen_per_rit)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)