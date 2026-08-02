import requests
import time
import psycopg2
import os
import json
import redis
from datetime import datetime

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=6379,
    decode_responses=True
)

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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS targets (
                id SERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
        """)
        conn.commit()
        cursor.close()
        conn.close()

def publish_to_redis(result: dict):
    try:
        redis_client.publish("alerts", json.dumps(result))
        print(f"[ALERT PUBLISHED] {result['url']}")
    except Exception as e:
        print(f"Failed to publish to redis: {e}")

def get_all_targets():
    conn = connect_db()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT targets.url, users.email FROM targets JOIN users ON targets.owner_id = users.id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [{"url": row[0], "owner_email": row[1]} for row in rows]



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


def run_checker(interval=30):
    while True:
        targets = get_all_targets()
        for target in targets:
            result = check_url(target["url"])
            result["owner_email"] = target["owner_email"]
            save_results(result)
            print(result)
            if result.get("status") == "down":
                publish_to_redis(result)
        time.sleep(interval)

if __name__ == "__main__":
    init_db()
    run_checker(interval=30)