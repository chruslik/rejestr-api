from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from psycopg2.extras import RealDictCursor
import os  # ← to jest wymagane
import traceback
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)
load_dotenv()

# Klucze Supabase z Environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route("/")
def index():
    return {"status": "ok", "message": "API działa"}
   

@app.route("/naprawy", methods=["GET"])
def pobierz_naprawy():
    try:
        query = supabase.table("naprawy").select(
            """
            id,
            status,
            data_przyjecia,
            data_zakonczenia,
            usterka,
            opis,
            klient:klienci(nazwa),
            maszyna:maszyny(marka, klasa, numer_seryjny)
            """
        )

        klient = request.args.get("klient")
        marka = request.args.get("marka")
        klasa = request.args.get("klasa")
        sn = request.args.get("sn")
        status = request.args.get("status")
        usterka = request.args.get("usterka")

        if klient:
            query = query.ilike("klienci.nazwa", f"%{klient}%")
        if marka:
            query = query.ilike("maszyny.marka", f"%{marka}%")
        if klasa:
            query = query.ilike("maszyny.klasa", f"%{klasa}%")
        if sn:
            query = query.ilike("maszyny.numer_seryjny", f"%{sn}%")
        if status:
            query = query.eq("status", status)
        if usterka:
            query = query.ilike("usterka", f"%{usterka}%")
        response = query.execute()

        if response.error:
            return jsonify({"error": response.error.message}), 500

        wyniki = []
        for row in response.data:
            wyniki.append({
                "id": row["id"],
                "status": row["status"],
                "data_przyjecia": row["data_przyjecia"],
                "data_zakonczenia": row["data_zakonczenia"],
                "usterka": row["usterka"],
                "opis": row["opis"],
                "klient": row["klient"]["nazwa"] if row.get("klient") else None,
                "marka": row["maszyna"]["marka"] if row.get("maszyna") else None,
                "klasa": row["maszyna"]["klasa"] if row.get("maszyna") else None,
                "sn": row["maszyna"]["numer_seyjny"] if row.get("maszyna") else None,
            })

        return jsonify(wyniki)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/naprawy", methods=["POST"])
def dodaj_naprawe_prosto():
    try:
        dane = request.get_json()

        # Walidacja
        if not dane.get("maszyna_id") or not dane.get("data_przyjecia") or not dane.get("status"):
            return jsonify({"error": "Brak wymaganych danych"}), 400

        # Dodanie naprawy
        supabase.table("naprawy").insert({
            "maszyna_id": dane["maszyna_id"],
            "data_przyjecia": dane["data_przyjecia"],
            "data_zakonczenia": dane.get("data_zakonczenia"),
            "status": dane["status"],
            "usterka": dane.get("usterka"),
            "opis": dane.get("opis")
        }).execute()

        return jsonify({"sukces": True})
    except Exception as e:
        print("Błąd w dodaj_naprawe:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/naprawy/<int:naprawa_id>", methods=["DELETE"])
def delete_naprawa(naprawa_id):
    try:
        result = supabase.table("naprawy").delete().eq("id", naprawa_id).execute()

        if result.data:
            return jsonify({"message": "Usunięto naprawę"})
        else:
            return jsonify({"error": "Nie znaleziono naprawy"}), 404
    except Exception as e:
        print("Błąd w delete_naprawa:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/naprawy/<int:naprawa_id>", methods=["PUT"])
def update_naprawa(naprawa_id):
    data = request.get_json()

    try:
        result = supabase.table("naprawy").update({
            "status": data.get("status"),
            "data_zakonczenia": data.get("data_zakonczenia"),
            "usterka": data.get("usterka"),
            "opis": data.get("opis")
        }).eq("id", naprawa_id).execute()

        if result.data:
            return jsonify({"message": "Zaktualizowano naprawę"})
        else:
            return jsonify({"error": "Nie znaleziono naprawy"}), 404
    except Exception as e:
        print("Błąd w update_naprawa:", e)
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

        # Sprawdź czy maszyna już istnieje
        existing = supabase.table("maszyny") \
            .select("id") \
            .eq("klient_id", klient_id) \
            .eq("numer_seryjny", numer_seryjny) \
            .limit(1) \
            .execute()

        if existing.data:
            return jsonify({"id": existing.data[0]["id"]})

        # Wstaw nową maszynę
        insert = supabase.table("maszyny").insert({
            "klient_id": klient_id,
            "marka": marka,
            "klasa": klasa,
            "numer_seryjny": numer_seryjny
        }).execute()

        return jsonify({"id": insert.data[0]["id"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/klienci", methods=["POST"])
def dodaj_klienta():
    try:
        data = request.get_json()
        nazwa = data.get("nazwa")
        if not nazwa:
            return jsonify({"error": "Brak nazwy klienta"}), 400

        # Sprawdź, czy klient już istnieje
        existing = supabase.table("klienci") \
            .select("id") \
            .eq("nazwa", nazwa) \
            .limit(1) \
            .execute()

        if existing.data:
            return jsonify({"id": existing.data[0]["id"]})

        # Dodaj nowego klienta
        insert = supabase.table("klienci").insert({"nazwa": nazwa}).execute()
        return jsonify({"id": insert.data[0]["id"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/slowniki")
def get_slowniki():
    try:
        marki = supabase.table("maszyny").select("marka").execute()
        klasy = supabase.table("maszyny").select("klasa").execute()
        usterki = supabase.table("naprawy").select("usterka").execute()
        klienci = supabase.table("klienci").select("nazwa").execute()
        numery_seryjne = supabase.table("maszyny").select("numer_seryjny").execute()

        return jsonify({
            "marki": list(set([row["marka"] for row in marki.data if row["marka"]])),
            "klasy": list(set([row["klasa"] for row in klasy.data if row["klasa"]])),
            "usterki": list(set([row["usterka"] for row in usterki.data if row["usterka"]])),
            "klienci": [row["nazwa"] for row in klienci.data],
            "numery_seryjne": [row["numer_seryjny"] for row in numery_seryjne.data]
        })
    except Exception as e:
        print("Błąd:", e)
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
       port = int(os.environ.get("PORT", 5000))
       app.run(host="0.0.0.0", port=port)
