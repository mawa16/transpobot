"""
TranspoBot — Backend FastAPI corrigé
Projet GLSi L3 — ESP/UCAD
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pymysql
import pymysql.cursors
import os
from dotenv import load_dotenv
load_dotenv()
import re
import json
import httpx

app = FastAPI(title="TranspoBot API", version="1.0.0")

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# servir les fichiers statiques (CSS, JS…)
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

# route principale → afficher index.html
@app.get("/")
def read_index():
    return FileResponse("frontend/index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuration ──────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "user":     os.getenv("DB_USER", "transpobot"),
    "password": os.getenv("DB_PASSWORD", "transpobot123"),
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

SYSTEM_PROMPT =f"""Tu es TranspoBot, assistant de gestion de transport.

{DB_SCHEMA}

RÈGLES :
1. Génère UNIQUEMENT des requêtes SELECT.
2. Réponds TOUJOURS en JSON :
   {{"sql": "SELECT ...", "explication": "réponse courte et directe"}}
3. L'explication doit être TRÈS COURTE et DIRECTE, max 1 phrase.
   Exemples :
   - "7 véhicules sont actifs."
   - "DIOP Mamadou avec 8 trajets."
   - "2 véhicules en maintenance : DK-9012-EF et DK-8901-ST."
4. PAS de description de la requête SQL dans l'explication.
5. Limite les résultats à 100 lignes avec LIMIT.
"""
# ── Connexion MariaDB/MySQL ────────────────────────────────────
def get_db():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        cursorclass=pymysql.cursors.DictCursor
    )

def execute_query(sql: str):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            results = cursor.fetchall()
            # Convertir en liste de dicts sérialisables
            return [
                {k: (v.isoformat() if hasattr(v, 'isoformat') else v) 
                 for k, v in row.items()}
                for row in results
            ]
    finally:
        conn.close()
# ── Appel LLM ─────────────────────────────────────────────────
async def ask_llm(question: str) -> dict:
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
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        # Nettoyer les balises markdown ```json
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        content = content.strip()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError("Réponse LLM invalide")
# ── Routes API ─────────────────────────────────────────────────
class ChatMessage(BaseModel):
    question: str

@app.post("/api/chat")
async def chat(msg: ChatMessage):
    try:
        llm_response = await ask_llm(msg.question)
        sql = llm_response.get("sql")
        explication = llm_response.get("explication", "")
        if not sql:
            return {"answer": explication, "data": [], "sql": None}
        data = execute_query(sql)
        return {
            "answer": explication,
            "data": data,
            "sql": sql,
            "count": len(data),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
def get_stats():
    stats = {}
    queries = {
        "total_trajets":     "SELECT COUNT(*) as n FROM trajets WHERE statut='termine'",
        "trajets_en_cours":  "SELECT COUNT(*) as n FROM trajets WHERE statut='en_cours'",
        "vehicules_actifs":  "SELECT COUNT(*) as n FROM vehicules WHERE statut='actif'",
        "incidents_ouverts": "SELECT COUNT(*) as n FROM incidents WHERE resolu=FALSE",
        "recette_totale":    "SELECT COALESCE(SUM(recette),0) as n FROM trajets WHERE statut='termine'",
        "total_passagers":   "SELECT COALESCE(SUM(nb_passagers),0) as n FROM trajets WHERE statut='termine'",
    }
    for key, sql in queries.items():
        result = execute_query(sql)
        stats[key] = result[0]["n"] if result else 0
    return stats

@app.get("/api/vehicules")
def get_vehicules():
    return execute_query("SELECT * FROM vehicules ORDER BY immatriculation")

@app.get("/api/chauffeurs")
def get_chauffeurs():
    return execute_query("""
        SELECT c.*, v.immatriculation
        FROM chauffeurs c
        LEFT JOIN vehicules v ON c.vehicule_id = v.id
        ORDER BY c.nom
    """)

@app.get("/api/trajets/recent")
def get_trajets_recent():
    return execute_query("""
        SELECT t.*, l.nom as ligne, ch.nom as chauffeur_nom,
               v.immatriculation
        FROM trajets t
        JOIN lignes l ON t.ligne_id = l.id
        JOIN chauffeurs ch ON t.chauffeur_id = ch.id
        JOIN vehicules v ON t.vehicule_id = v.id
        ORDER BY t.date_heure_depart DESC
        LIMIT 20
    """)

@app.get("/api/incidents")
def get_incidents():
    return execute_query("""
        SELECT i.*, t.date_heure_depart, l.nom as ligne
        FROM incidents i
        JOIN trajets t ON i.trajet_id = t.id
        JOIN lignes l ON t.ligne_id = l.id
        ORDER BY i.date_incident DESC
        LIMIT 20
    """)

@app.get("/health")
def health():
    return {"status": "ok", "app": "TranspoBot"}

# ── Lancement ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
