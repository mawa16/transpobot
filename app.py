"""
TranspoBot — Backend FastAPI complet
Projet GLSi L3 — ESP/UCAD
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error as MySQLError
import os
import re
import json
import httpx

load_dotenv()

app = FastAPI(title="TranspoBot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuration ──────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "transpobot"),
}

LLM_API_KEY  = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL    = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

# ── Schéma de la base (pour le prompt système) ─────────────────
DB_SCHEMA = """
Tables MySQL disponibles :

vehicules(id, immatriculation, type[bus/minibus/taxi], capacite, statut[actif/maintenance/hors_service], kilometrage, date_acquisition)
chauffeurs(id, nom, prenom, telephone, numero_permis, categorie_permis, disponibilite, vehicule_id, date_embauche)
lignes(id, code, nom, origine, destination, distance_km, duree_minutes)
tarifs(id, ligne_id, type_client[normal/etudiant/senior], prix)
trajets(id, ligne_id, chauffeur_id, vehicule_id, date_heure_depart, date_heure_arrivee, statut[planifie/en_cours/termine/annule], nb_passagers, recette)
incidents(id, trajet_id, type[panne/accident/retard/autre], description, gravite[faible/moyen/grave], date_incident, resolu)
"""

SYSTEM_PROMPT = f"""Tu es TranspoBot, l'assistant intelligent de la compagnie de transport.
Tu aides les gestionnaires à interroger la base de données en langage naturel.

{DB_SCHEMA}

RÈGLES IMPORTANTES :
1. Génère UNIQUEMENT des requêtes SELECT (jamais INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE).
2. Réponds TOUJOURS en JSON valide avec ce format exact :
   {{"sql": "SELECT ...", "explication": "Ce que fait la requête"}}
3. Si la question ne peut pas être répondue avec SQL, réponds :
   {{"sql": null, "explication": "Explication de pourquoi"}}
4. Utilise des alias clairs dans les requêtes (AS nom_colonne).
5. Limite toujours les résultats avec LIMIT 100 maximum.
6. Pour les jointures, utilise toujours des alias de table (ex: t pour trajets, c pour chauffeurs).
7. Les champs booléens en MySQL sont 0/1 (utilise resolu=0 ou resolu=1, pas TRUE/FALSE).
"""

# ── Sécurité SQL ───────────────────────────────────────────────
FORBIDDEN_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|EXEC|EXECUTE|GRANT|REVOKE)\b',
    re.IGNORECASE
)

def is_safe_sql(sql: str) -> bool:
    """Vérifie que la requête est bien un SELECT sans mots-clés dangereux."""
    cleaned = sql.strip().upper()
    if not cleaned.startswith("SELECT"):
        return False
    if FORBIDDEN_KEYWORDS.search(sql):
        return False
    return True

# ── Connexion MySQL ────────────────────────────────────────────
def get_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except MySQLError as e:
        raise HTTPException(status_code=503, detail=f"Connexion base de données impossible : {e}")

def execute_query(sql: str) -> list:
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        # Convertir les types non-sérialisables (Decimal, date, etc.)
        import decimal
        import datetime
        def serialize(obj):
            if isinstance(obj, decimal.Decimal):
                return float(obj)
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()
            return obj
        return [{k: serialize(v) for k, v in row.items()} for row in rows]
    except MySQLError as e:
        raise HTTPException(status_code=400, detail=f"Erreur SQL : {e}")
    finally:
        cursor.close()
        conn.close()

# ── Appel LLM ─────────────────────────────────────────────────
async def ask_llm(question: str) -> dict:
    if not LLM_API_KEY:
        raise HTTPException(status_code=500, detail="Clé API LLM non configurée (OPENAI_API_KEY)")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": question},
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
                timeout=30,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            # Nettoyage des éventuels blocs markdown ```json
            content = re.sub(r'```json\s*|\s*```', '', content).strip()
            return json.loads(content)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Le LLM n'a pas répondu à temps (timeout 30s)")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Erreur API LLM : {e.response.status_code}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Le LLM a renvoyé un JSON invalide")

# ── Routes API ─────────────────────────────────────────────────

class ChatMessage(BaseModel):
    question: str

@app.post("/api/chat")
async def chat(msg: ChatMessage):
    """Point d'entrée principal : question en langage naturel → SQL → résultats."""
    if not msg.question.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide")

    llm_response = await ask_llm(msg.question)
    sql        = llm_response.get("sql")
    explication = llm_response.get("explication", "")

    if not sql:
        return {"answer": explication, "data": [], "sql": None}

    # Double vérification de sécurité côté serveur
    if not is_safe_sql(sql):
        raise HTTPException(
            status_code=400,
            detail="Requête refusée : seules les requêtes SELECT sont autorisées"
        )

    data = execute_query(sql)
    return {
        "answer": explication,
        "data":   data,
        "sql":    sql,
        "count":  len(data),
    }


@app.get("/api/stats")
def get_stats():
    """Tableau de bord — indicateurs clés (KPI)."""
    queries = {
        "total_trajets":     "SELECT COUNT(*) AS n FROM trajets WHERE statut='termine'",
        "trajets_en_cours":  "SELECT COUNT(*) AS n FROM trajets WHERE statut='en_cours'",
        "trajets_planifies": "SELECT COUNT(*) AS n FROM trajets WHERE statut='planifie'",
        "vehicules_actifs":  "SELECT COUNT(*) AS n FROM vehicules WHERE statut='actif'",
        "vehicules_maintenance": "SELECT COUNT(*) AS n FROM vehicules WHERE statut='maintenance'",
        "chauffeurs_disponibles": "SELECT COUNT(*) AS n FROM chauffeurs WHERE disponibilite=1",
        "incidents_ouverts": "SELECT COUNT(*) AS n FROM incidents WHERE resolu=0",
        "recette_totale":    "SELECT COALESCE(SUM(recette), 0) AS n FROM trajets WHERE statut='termine'",
        "recette_semaine":   """
            SELECT COALESCE(SUM(recette), 0) AS n FROM trajets
            WHERE statut='termine' AND date_heure_depart >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """,
    }
    stats = {}
    for key, sql in queries.items():
        result = execute_query(sql)
        stats[key] = result[0]["n"] if result else 0
    return stats


@app.get("/api/vehicules")
def get_vehicules():
    """Liste complète des véhicules."""
    return execute_query("SELECT * FROM vehicules ORDER BY immatriculation")


@app.get("/api/chauffeurs")
def get_chauffeurs():
    """Liste des chauffeurs avec leur véhicule assigné."""
    return execute_query("""
        SELECT c.id, c.nom, c.prenom, c.telephone, c.numero_permis,
               c.categorie_permis, c.disponibilite, c.date_embauche,
               v.immatriculation AS vehicule, v.type AS type_vehicule
        FROM chauffeurs c
        LEFT JOIN vehicules v ON c.vehicule_id = v.id
        ORDER BY c.nom, c.prenom
    """)


@app.get("/api/lignes")
def get_lignes():
    """Liste des lignes avec leurs tarifs."""
    return execute_query("""
        SELECT l.*, 
               MAX(CASE WHEN t.type_client='normal'   THEN t.prix END) AS tarif_normal,
               MAX(CASE WHEN t.type_client='etudiant' THEN t.prix END) AS tarif_etudiant,
               MAX(CASE WHEN t.type_client='senior'   THEN t.prix END) AS tarif_senior
        FROM lignes l
        LEFT JOIN tarifs t ON l.id = t.ligne_id
        GROUP BY l.id
        ORDER BY l.code
    """)


@app.get("/api/incidents")
def get_incidents():
    """Incidents récents avec détails du trajet."""
    return execute_query("""
        SELECT i.id, i.type, i.description, i.gravite, i.date_incident, i.resolu,
               l.nom AS ligne, ch.nom AS chauffeur_nom, ch.prenom AS chauffeur_prenom,
               v.immatriculation
        FROM incidents i
        JOIN trajets   tr ON i.trajet_id   = tr.id
        JOIN lignes    l  ON tr.ligne_id   = l.id
        JOIN chauffeurs ch ON tr.chauffeur_id = ch.id
        JOIN vehicules v  ON tr.vehicule_id  = v.id
        ORDER BY i.date_incident DESC
        LIMIT 50
    """)


@app.get("/api/trajets/recent")
def get_trajets_recent():
    """20 derniers trajets avec informations complètes."""
    return execute_query("""
        SELECT t.id, t.date_heure_depart, t.date_heure_arrivee, t.statut,
               t.nb_passagers, t.recette,
               l.code AS ligne_code, l.nom AS ligne_nom,
               ch.nom AS chauffeur_nom, ch.prenom AS chauffeur_prenom,
               v.immatriculation, v.type AS type_vehicule
        FROM trajets t
        JOIN lignes    l  ON t.ligne_id    = l.id
        JOIN chauffeurs ch ON t.chauffeur_id = ch.id
        JOIN vehicules v  ON t.vehicule_id  = v.id
        ORDER BY t.date_heure_depart DESC
        LIMIT 20
    """)


@app.get("/health")
def health():
    """Vérification de l'état de l'API et de la connexion DB."""
    try:
        conn = get_db()
        conn.close()
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {
        "status": "ok",
        "app":    "TranspoBot",
        "db":     db_status,
        "model":  LLM_MODEL,
    }


# ── Lancement ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
