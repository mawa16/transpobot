"""
TranspoBot — Backend FastAPI
Projet GLSi L3 — ESP/UCAD
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pymysql
import pymysql.cursors
import os
from dotenv import load_dotenv
import re
import json
import httpx

load_dotenv()

app = FastAPI(title="TranspoBot API", version="1.0.0")

# ── Static files ─────────────────────────────
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
def read_index():
    return FileResponse("frontend/index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB CONFIG ────────────────────────────────
DB_CONFIG = {
    'host': os.getenv("MYSQLHOST"),
    'user': os.getenv("MYSQLUSER"),
    'password': os.getenv("MYSQLPASSWORD"),
    'database': os.getenv("MYSQLDATABASE") or "railway",
    'port': int(os.getenv("MYSQLPORT", 3306)),
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': True,
    'charset': 'utf8mb4'
}

def get_db():
    return pymysql.connect(**DB_CONFIG)

def execute_query(sql):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()
    finally:
        conn.close()

# ── IA CONFIG ───────────────────────────────
LLM_API_KEY  = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL    = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

DB_SCHEMA = """
vehicules(id, immatriculation, statut)
chauffeurs(id, nom, prenom)
trajets(id, date_heure_depart, statut, nb_passagers, recette)
incidents(id, gravite, resolu)
"""

SYSTEM_PROMPT = f"""
Tu es TranspoBot.

{DB_SCHEMA}

RÈGLES :
- Génère uniquement des requêtes SELECT
- Réponds en JSON : {{"sql":"...","explication":"..."}}
- Explication courte
- Toujours LIMIT 100
- IMPORTANT :
  - recettes => statut = 'termine'
  - utiliser CURDATE() pour dates dynamiques
"""

async def ask_llm(question):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                "temperature": 0
            }
        )
        content = response.json()["choices"][0]["message"]["content"]
        content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        return json.loads(content)

# ── API CHAT ────────────────────────────────
class ChatMessage(BaseModel):
    question: str

@app.post("/api/chat")
async def chat(msg: ChatMessage):
    try:
        res = await ask_llm(msg.question)
        sql = res.get("sql")
        data = execute_query(sql) if sql else []
        return {
            "answer": res.get("explication"),
            "data": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── STATS ───────────────────────────────────
@app.get("/api/stats")
def get_stats():
    stats = {}

    queries = {
        "total_trajets": "SELECT COUNT(*) n FROM trajets WHERE statut='termine'",
        "trajets_en_cours": "SELECT COUNT(*) n FROM trajets WHERE statut='en_cours'",
        "vehicules_actifs": "SELECT COUNT(*) n FROM vehicules WHERE statut='actif'",
        "incidents_ouverts": "SELECT COUNT(*) n FROM incidents WHERE resolu=FALSE",
        "recette_totale": "SELECT SUM(recette) n FROM trajets WHERE statut='termine'",
        "total_passagers": "SELECT SUM(nb_passagers) n FROM trajets WHERE statut='termine'",

        # dynamique
        "recette_mois": """
        SELECT COALESCE(SUM(recette),0) n
        FROM trajets
        WHERE MONTH(date_heure_depart)=MONTH(CURDATE())
        AND YEAR(date_heure_depart)=YEAR(CURDATE())
        AND statut='termine'
        """
    }

    for k, q in queries.items():
        res = execute_query(q)
        stats[k] = res[0]["n"] if res and res[0]["n"] else 0

    return stats
