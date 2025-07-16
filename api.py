from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
CORS(app) # pozwala na połączenie z Kivy na Androidzie

DB_PATH = "rejestr.db"

def connect_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with connect_db() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS klienci (id INTEGER PRIMARY KEY, nazwa TEXT)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS maszyny (
                id INTEGER PRIMARY KEY,
                klient_id INTEGER,
                marka TEXT,
                klasa TEXT,
                numer_seryjny TEXT,
                FOREIGN KEY (klient_id) REFERENCES klienci(id)
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS naprawy (
                id INTEGER PRIMARY KEY,
                maszyna_id INTEGER,
                data_przyjecia TEXT,
                data_zakonczenia TEXT,
                status TEXT,
                usterka TEXT,
                opis TEXT,
                FOREIGN KEY (maszyna_id) REFERENCES maszyny(id)
            )""")
        conn.commit()

@app.route("/naprawy", methods=["GET"])
def get_naprawy():
    query = """SELECT n.id, k.nazwa, m.marka, m.klasa, m.numer_seryjny,
                      n.status, n.data_przyjecia, n.data_zakonczenia,
                      n.usterka, n.opis
               FROM naprawy n
               JOIN maszyny m ON n.maszyna_id = m.id
               JOIN klienci k ON m.klient_id = k.id
               ORDER BY n.id DESC"""
    with connect_db() as conn:
        rows = conn.execute(query).fetchall()
    return jsonify([dict(zip(["id", "klient", "marka", "klasa", "sn", "status", "data_przyjecia", "data_zakonczenia", "usterka", "opis"], row)) for row in rows])

@app.route("/naprawy", methods=["POST"])
def add_naprawa():
    data = request.json
    klient = data["klient"].strip()
    marka = data.get("marka", "").strip()
    klasa = data.get("klasa", "").strip()
    sn = data["sn"].strip()
    usterka = data.get("usterka", "").strip()
    opis = data.get("opis", "").strip()
    data_przyjecia = data.get("data_przyjecia", datetime.now().strftime("%Y-%m-%d"))

    with connect_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT id FROM klienci WHERE nazwa=?", (klient,))
        row = cur.fetchone()
        klient_id = row[0] if row else cur.execute("INSERT INTO klienci (nazwa) VALUES (?)", (klient,)).lastrowid

        cur.execute("SELECT id FROM maszyny WHERE numer_seryjny=? AND klient_id=?", (sn, klient_id))
        row = cur.fetchone()
        maszyna_id = row[0] if row else cur.execute(
            "INSERT INTO maszyny (klient_id, marka, klasa, numer_seryjny) VALUES (?, ?, ?, ?)",
            (klient_id, marka, klasa, sn)).lastrowid

        cur.execute("INSERT INTO naprawy (maszyna_id, data_przyjecia, status, usterka, opis) VALUES (?, ?, 'nowa', ?, ?)",
                    (maszyna_id, data_przyjecia, usterka, opis))
        conn.commit()

    return jsonify({"message": "Naprawa dodana"}), 201

@app.route("/naprawy/<int:naprawa_id>", methods=["PUT"])
def update_naprawa(naprawa_id):
    data = request.json
    status = data.get("status")
    data_zak = data.get("data_zakonczenia")
    usterka = data.get("usterka")
    opis = data.get("opis")

    with connect_db() as conn:
        conn.execute("""UPDATE naprawy SET status=?, data_zakonczenia=?, usterka=?, opis=? WHERE id=?""",
                     (status, data_zak, usterka, opis, naprawa_id))
        conn.commit()

    return jsonify({"message": "Zaktualizowano naprawę"})

@app.route("/naprawy/<int:naprawa_id>", methods=["DELETE"])
def delete_naprawa(naprawa_id):
    with connect_db() as conn:
        conn.execute("DELETE FROM naprawy WHERE id=?", (naprawa_id,))
        conn.commit()
    return jsonify({"message": "Usunięto naprawę"})

@app.route("/slowniki", methods=["GET"])
def get_slowniki():
    with connect_db() as conn:
        marki = [row[0] for row in conn.execute("SELECT DISTINCT marka FROM maszyny")]
        klasy = [row[0] for row in conn.execute("SELECT DISTINCT klasa FROM maszyny")]
        usterki = [row[0] for row in conn.execute("SELECT DISTINCT usterka FROM naprawy")]
        klienci = [row[0] for row in conn.execute("SELECT nazwa FROM klienci")]
    return jsonify({"marki": marki, "klasy": klasy, "usterki": usterki, "klienci": klienci})

if _name_ == "_main_":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

