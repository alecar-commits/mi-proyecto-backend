from fastapi import FastAPI
import psycopg2
import os

app = FastAPI()

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@app.get("/")
def home():
    return {"status": "ok"}

@app.get("/grants")
def get_grants():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS grants (
        id SERIAL PRIMARY KEY,
        title TEXT,
        link TEXT,
        score INT
    );
    """)

    cur.execute("SELECT title, link, score FROM grants LIMIT 20;")
    rows = cur.fetchall()

    conn.commit()
    conn.close()

    return rows
