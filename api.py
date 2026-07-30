from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import psycopg2
import os

app = FastAPI()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": 5432,
    "database": os.getenv("POSTGRES_DB", "sentinel"),
    "user": os.getenv("POSTGRES_USER", "sentinel"),
    "password": os.getenv("POSTGRES_PASSWORD", "sentinel"),
}

@app.get("/status")
def get_status():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""SELECT DISTINCT ON (url) url, status, status_code, response_time_ms, error, checked_at 
        FROM checks 
        ORDER BY url, checked_at DESC""")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        results = []
        for row in rows:
            results.append({
                "url": row[0],
                "status": row[1],
                "status_code": row[2],
                "response_time_ms": row[3],
                "error": row[4],
                "checked_at": row[5].isoformat() if row[5] else None
            })
        return results
    except Exception as e:
        return {"error": str(e)}    

app.mount("/", StaticFiles(directory="static", html=True), name="static")
