from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter
from auth import hash_password, verify_password, create_access_token, decode_access_token
from fastapi import FastAPI, Response, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import psycopg2
import os

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

class UserRegister(BaseModel):
    username: str
    password: str
    email: str

class TargetCreate(BaseModel):
    url: str

app = FastAPI()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": 5432,
    "database": os.getenv("POSTGRES_DB", "sentinel"),
    "user": os.getenv("POSTGRES_USER", "sentinel"),
    "password": os.getenv("POSTGRES_PASSWORD", "sentinel"),
}


@app.post("/register")
def register_user(user: UserRegister):
    # Implementation for user registration
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    try:
        hashed = hash_password(user.password)
        cursor.execute("INSERT INTO users (username, hashed_password, email) VALUES (%s, %s, %s)", (user.username, hashed, user.email))
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        cursor.close()
        conn.close()
    return {"message": "User registered successfully"}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Implementation for user login
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT hashed_password FROM users WHERE username = %s", (form_data.username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row or not verify_password(form_data.password, row[0]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    token = create_access_token({"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}

def get_current_user_id(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token or expired token")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (payload["sub"],))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return row[0]

@app.post("/targets")
def add_target(target: TargetCreate, current_user_id: int = Depends(get_current_user_id)):
    # Implementation for creating a new target
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO targets (url, owner_id) VALUES (%s, %s) RETURNING id", (target.url, current_user_id))
    new_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return {"id": new_id, "url": target.url}

@app.get("/targets")
def get_targets(current_user_id: int = Depends(get_current_user_id)):
    # Implementation for retrieving targets
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, created_at FROM targets WHERE owner_id = %s", (current_user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [{"id": row[0], "url": row[1], "created_at": row[2]} for row in rows]

@app.delete("/targets/{target_id}")
def delete_target(target_id: int, current_user_id: int = Depends(get_current_user_id)):
    # Implementation for deleting a target
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM targets WHERE id = %s AND owner_id = %s",
    (target_id, current_user_id)
    )
    deleted = cursor.rowcount()
    conn.commit()
    cursor.close()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Target not found or not yours.")
    return {"message": "Target deleted successfully"}

check_requests_total = Counter(
    "sentinel_status_requests_total",
    "Total number of /status requests"
)

@app.get("/status")
def get_status():
    check_requests_total.inc()
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


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.mount("/", StaticFiles(directory="static", html=True), name="static")
