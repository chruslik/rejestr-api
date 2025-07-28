from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os  # ← to jest wymagane
import traceback

app = Flask(__name__)
CORS(app)

DATABASE_URL = "postgresql://postgres.njnotdsifzblpnlfulau:sb_secret_jYSXXP-r7B8nzr2B1aTIJA_sOzozlnH@aws-0-eu-north-1.pooler.supabase.com:5432/postgres"

def connect_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    with connect_db() as conn:
        with conn.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS klienci (
                    id SERIAL PRIMARY KEY,
                    nazwa VARCHAR
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS maszyny (
                    id SERIAL PRIMARY KEY,
                    klient_id INTEGER REFERENCES klienci(id),
                    marka VARCHAR,
                    klasa VARCHAR,
                    numer_seryjny VARCHAR
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS naprawy (
                    id SERIAL PRIMARY KEY,
                    maszyna_id INTEGER REFERENCES maszyny(id),
                    data_przyjecia DATE,
                    data_zakonczenia DATE,
                    status VARCHAR,
                    usterka TEXT,
                    opis TEXT
                )
            """)
            conn.commit()

@app.route("/naprawy", methods=["GET"])
def get_naprawy():
    try:
        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT n.id, k.nazwa AS klient, m.marka, m.klasa, m.numer_seryjny AS sn,
                       n.status, n.data_przyjecia, n.data_zakonczenia,
                       n.usterka, n.opis
                FROM naprawy n
                JOIN maszyny m ON n.maszyna_id = m.id
                JOIN klienci k ON m.klient_id = k.id
                ORDER BY n.id DESC
            """)
            return jsonify(cur.fetchall())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/naprawy", methods=["POST"])
def dodaj_naprawe():
    try:
        dane = request.json
        with connect_db() as conn:
            cur = conn.cursor()

            # Szukamy istniejącego klienta
            cur.execute("SELECT id FROM klienci WHERE nazwa = %s", (dane["klient"],))
            klient = cur.fetchone()
            if klient:
                klient_id = klient["id"]
            else:
                cur.execute("INSERT INTO klienci (nazwa) VALUES (%s) RETURNING id", (dane["klient"],))
                klient_id = cur.fetchone()["id"]

            # Szukamy istniejącej maszyny
            cur.execute("""
                SELECT id FROM maszyny
                WHERE klient_id = %s AND marka = %s AND klasa = %s AND numer_seryjny = %s
            """, (klient_id, dane["marka"], dane["klasa"], dane["sn"]))
            maszyna = cur.fetchone()
            if maszyna:
                maszyna_id = maszyna["id"]
            else:
                cur.execute("""
                    INSERT INTO maszyny (klient_id, marka, klasa, numer_seryjny)
                    VALUES (%s, %s, %s, %s) RETURNING id
                """, (klient_id, dane["marka"], dane["klasa"], dane["sn"]))
                maszyna_id = cur.fetchone()["id"]

            cur.execute("""
                INSERT INTO naprawy (maszyna_id, data_przyjecia, data_zakonczenia, status, usterka, opis)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                maszyna_id,
                dane["data_przyjecia"],
                dane.get("data_zakonczenia"),
                dane["status"],
                dane["usterka"],
                dane["opis"]
            ))
            conn.commit()
            return jsonify({"sukces": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/naprawy/<int:naprawa_id>", methods=["DELETE"])
def delete_naprawa(naprawa_id):
    try:
        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM naprawy WHERE id = %s", (naprawa_id,))
            conn.commit()
        return jsonify({"message": "Usunięto naprawę"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/naprawy/<int:naprawa_id>", methods=["PUT"])
def update_naprawa(naprawa_id):
    data = request.get_json()
    status = data.get("status")
    data_zak = data.get("data_zakonczenia")
    usterka = data.get("usterka")
    opis = data.get("opis")

    try:
        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE naprawy 
                SET status = %s, data_zakonczenia = %s, usterka = %s, opis = %s 
                WHERE id = %s
            """, (status, data_zak, usterka, opis, naprawa_id))
            conn.commit()
        return jsonify({"message": "Zaktualizowano naprawę"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/maszyny", methods=["GET"])
def get_maszyny():
    try:
        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM maszyny")
            return jsonify(cur.fetchall())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/maszyny", methods=["POST"])
def dodaj_lub_pobierz_maszyne():
    try:
        data = request.get_json()
        klient_id = data.get("klient_id")
        marka = data.get("marka")
        klasa = data.get("klasa")
        numer_seryjny = data.get("numer_seryjny")

        if not klient_id or not numer_seryjny:
            return jsonify({"error": "Brak wymaganych danych"}), 400

        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id FROM maszyny
                WHERE klient_id = %s AND numer_seryjny = %s
            """, (klient_id, numer_seryjny))
            row = cur.fetchone()
            if row:
                return jsonify({"id": row["id"]})

            cur.execute("""
                INSERT INTO maszyny (klient_id, marka, klasa, numer_seryjny)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (klient_id, marka, klasa, numer_seryjny))
            new_id = cur.fetchone()["id"]
            conn.commit()
            return jsonify({"id": new_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/klienci", methods=["POST"])
def dodaj_klienta():
    try:
        data = request.get_json()
        nazwa = data.get("nazwa")
        if not nazwa:
            return jsonify({"error": "Brak nazwy klienta"}), 400

        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM klienci WHERE nazwa = %s", (nazwa,))
            row = cur.fetchone()
            if row:
                return jsonify({"id": row["id"]})
            
            cur.execute("INSERT INTO klienci (nazwa) VALUES (%s) RETURNING id", (nazwa,))
            new_id = cur.fetchone()["id"]
            conn.commit()
            return jsonify({"id": new_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/slowniki", methods=["GET"])
def get_slowniki():
    try:
        with connect_db() as conn:
            cur = conn.cursor()

            cur.execute("SELECT DISTINCT marka FROM maszyny")
            marki = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT klasa FROM maszyny")
            klasy = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT usterka FROM naprawy")
            usterki = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT nazwa FROM klienci")
            klienci = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT numer_seryjny FROM maszyny")
            numery_seryjne = [row[0] for row in cur.fetchall()]

        return jsonify({
            "marki": marki,
            "klasy": klasy,
            "usterki": usterki,
            "klienci": klienci,
            "numery_seryjne": numery_seryjne
        })
    except Exception as e:
        print("Błąd w /slowniki:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/test-db", methods=["GET"])
def test_db():
    try:
        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            result = cur.fetchone()
        return jsonify({"status": "ok", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
       port = int(os.environ.get("PORT", 10000))
       app.run(host="0.0.0.0", port=port)
