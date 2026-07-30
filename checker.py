import requests
import time
import psycopg2
import os
from datetime import datetime

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": 5432,
    "database": os.getenv("POSTGRES_DB", "sentinel"),
    "user": os.getenv("POSTGRES_USER", "sentinel"),
    "password": os.getenv("POSTGRES_PASSWORD", "sentinel"),
}

def connect_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def init_db():
    conn = connect_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id SERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                status_code INT,
                response_time_ms FLOAT,
                error TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

def check_url(url):
    start_time = time.time()
    try:
        response = requests.get(url, timeout=5)
        elapsed = time.time() - start_time
        return {
            'url': url,
            "status": "up" if response.status_code < 400 else "down",
            "status_code": response.status_code,
            "response_time_ms": round(elapsed * 1000, 2)
        }
    
    except requests.exceptions.RequestException as e:
        return {
            'url': url,
            "status": "down",
            "error": str(e)
        }

def save_results(results: dict):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO checks (url, status, status_code, response_time_ms, error, checked_at) VALUES (%s, %s, %s, %s, %s, %s)",
        (
            results['url'],
            results.get('status'),
            results.get('status_code'),
            results.get('response_time_ms'),
            results.get('error'),
            datetime.now()
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


def run_checker(urls, interval=30):
    while True:
        for url in urls:
            result = check_url(url)
            save_results(result)
            print(result)
        time.sleep(interval)
if __name__ == "__main__":
    init_db()
    urls = [
        "https://www.suatdurkaya.dev",
        "https://www.bobsotfrs.com"
    ]
    run_checker(urls, interval=30)