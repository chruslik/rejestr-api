from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os
import requests

app = Flask(__name__)
CORS(app)


DB_PATH = "rejestr.db"

def connect_db():
    return sqlite3.connect(DB_PATH)

def fetch_db():
    if not os.path.exists(DB_PATH):
        print("Pobieram bazę z GitHub...")
        url = "https://raw.githubusercontent.com/chruslik/Rejestr_2/main/rejestr.db"
        r = requests.get(url)
        if r.status_code == 200:
            with open(DB_PATH, "wb") as f:
                f.write(r.content)
            print("Baza została pobrana.")
        else:
            print("Nie udało się pobrać bazy:", r.status_code)


def init_db():
    with connect_db() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS klienci (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nazwa TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS maszyny (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                klient_id INTEGER,
                marka TEXT,
                klasa TEXT,
                numer_seryjny TEXT,
                FOREIGN KEY (klient_id) REFERENCES klienci(id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS naprawy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                maszyna_id INTEGER,
                data_przyjecia TEXT,
                data_zakonczenia TEXT,
                status TEXT,
                usterka TEXT,
                opis TEXT,
                FOREIGN KEY (maszyna_id) REFERENCES maszyny(id)
            )
        """)
        conn.commit()

fetch_db()
init_db()

@app.route("/naprawy", methods=["GET"])
def get_naprawy():
    try:
        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute("""SELECT n.id, k.nazwa, m.marka, m.klasa, m.numer_seryjny,
                                  n.status, n.data_przyjecia, n.data_zakonczenia,
                                  n.usterka, n.opis
                           FROM naprawy n
                           JOIN maszyny m ON n.maszyna_id = m.id
                           JOIN klienci k ON m.klient_id = k.id
                           ORDER BY n.id DESC""")
            rows = cur.fetchall()
        return jsonify([
            dict(zip(["id", "klient", "marka", "klasa", "sn", "status", "data_przyjecia", "data_zakonczenia", "usterka", "opis"], row))
            for row in rows
        ])
    except Exception as e:
        print("Błąd:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/maszyny", methods=["GET"])
def get_maszyny():
    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM maszyny")
        maszyny = [dict(zip([col[0] for col in cur.description], row)) for row in cur.fetchall()]
    return jsonify(maszyny)

@app.route("/maszyny", methods=["POST"])
def dodaj_lub_pobierz_maszyne():
    data = request.get_json()
    klient_id = data.get("klient_id")
    marka = data.get("marka")
    klasa = data.get("klasa")
    numer_seryjny = data.get("numer_seryjny")

    if not klient_id or not numer_seryjny:
        return jsonify({"error": "Brak wymaganych danych"}), 400

    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM maszyny WHERE klient_id = ? AND numer_seryjny = ?", (klient_id, numer_seryjny))
        row = cur.fetchone()
        if row:
            return jsonify({"id": row[0]})
        cur.execute("INSERT INTO maszyny (klient_id, marka, klasa, numer_seryjny) VALUES (?, ?, ?, ?)",
                    (klient_id, marka, klasa, numer_seryjny))
        conn.commit()
        return jsonify({"id": cur.lastrowid})

@app.route("/naprawy", methods=["GET"])
def pobierz_naprawy():
    query = """
        SELECT n.id, k.nazwa AS klient, m.marka, m.klasa, m.numer_seryjny AS sn,
               n.status, n.data_przyjecia, n.data_zakonczenia, n.usterka, n.opis
        FROM naprawy n
        JOIN maszyny m ON n.maszyna_id = m.id
        JOIN klienci k ON m.klient_id = k.id
    """
    filters = []
    values = []

    if status := request.args.get("status"):
        filters.append("n.status = ?")
        values.append(status)
    if sn := request.args.get("sn"):
        filters.append("m.numer_seryjny = ?")
        values.append(sn)
    if usterka := request.args.get("usterka"):
        filters.append("n.usterka LIKE ?")
        values.append(f"%{usterka}%")
    if data_przyjecia := request.args.get("data_przyjecia"):
        filters.append("n.data_przyjecia = ?")
        values.append(data_przyjecia)
    if klasa := request.args.get("klasa"):
        filters.append("m.klasa = ?")
        values.append(klasa)
    if klient := request.args.get("klient"):
        filters.append("k.nazwa = ?")
        values.append(klient)
    if marka := request.args.get("marka"):
        filters.append("m.marka = ?")
        values.append(marka)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += " ORDER BY n.id DESC"

    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute(query, values)
        naprawy = [dict(zip([col[0] for col in cur.description], row)) for row in cur.fetchall()]
    return jsonify(naprawy)

@app.route("/klienci", methods=["POST"])
def dodaj_klienta():
    data = request.get_json()
    nazwa = data.get("nazwa")
    if not nazwa:
        return jsonify({"error": "Brak nazwy klienta"}), 400

    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM klienci WHERE nazwa = ?", (nazwa,))
        row = cur.fetchone()
        if row:
            return jsonify({"id": row[0]})
        cur.execute("INSERT INTO klienci (nazwa) VALUES (?)", (nazwa,))
        conn.commit()
        return jsonify({"id": cur.lastrowid})

@app.route("/naprawy", methods=["POST"])
def dodaj_naprawe():
    try:
        data = request.get_json()
        maszyna_id = data.get("maszyna_id")
        data_przyjecia = data.get("data_przyjecia")
        status = data.get("status", "nowa")
        usterka = data.get("usterka", "")
        opis = data.get("opis", "")

        if not maszyna_id or not data_przyjecia:
            return jsonify({"error": "Brak danych"}), 400

        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute("""INSERT INTO naprawy (maszyna_id, data_przyjecia, status, usterka, opis)
                           VALUES (?, ?, ?, ?, ?)""",
                        (maszyna_id, data_przyjecia, status, usterka, opis))
            conn.commit()
            return jsonify({"id": cur.lastrowid}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/naprawy/<int:naprawa_id>", methods=["PUT"])
def update_naprawa(naprawa_id):
    data = request.get_json()
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
        numery_seryjne = [row[0] for row in conn.execute("SELECT DISTINCT numer_seryjny FROM maszyny")]

    return jsonify({
        "marki": marki,
        "klasy": klasy,
        "usterki": usterki,
        "klienci": klienci,
        "numery_seryjne": numery_seryjne
    })

if  __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
