from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import google.generativeai as genai
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Permitir que tu Frontend en React se conecte sin bloqueos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de IA y Base de Datos
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

class ScrapeRequest(BaseModel):
    url: str
    foundationName: Optional[str] = None

@app.get("/")
def home():
    return {"status": "ok", "service": "UNITAS Funding Finder API"}

@app.post("/scrape")
async def start_scraping(request: ScrapeRequest):
    prompt = f"""
    Actúa como un analista de investigación élite para UNITAS Bolivia. 
    Tu misión es encontrar convocatorias VIGENTES y ACTIVAS en el sitio web de referencia: {request.url}
    
    Contexto adicional:
    - Instancia de Financiamiento: {request.foundationName or 'No especificado'}
    - Fecha de hoy: {datetime.now().strftime('%d/%m/%Y')}
    
    Reglas estrictas de validación:
    1. Encuentra solo convocatorias cuya fecha de cierre sea en el futuro o estén abiertas permanentemente.
    2. El campo 'enlace' debe llevar a la oportunidad específica.
    
    Devuelve la respuesta ÚNICAMENTE como un array de objetos JSON con las siguientes claves:
    "nombreConvocatoria", "areasTematicas", "dirigidoA", "fechaCierre", "paisRegion", "enlace"
    
    No incluyas texto introductorio, explicaciones ni marcadores como ```json. Devuelve solo el JSON puro.
    """
    
    try:
        response = model.generate_content(
            prompt,
            tools=[{'google_search': {}}]
        )
        
        import json
        text_response = response.text.strip()
        text_response = text_response.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_response)
        
        # Guardar automáticamente en Postgres cada resultado
        conn = get_conn()
        cur = conn.cursor()
        
        for item in data:
            cur.execute("""
                INSERT INTO grants (nombreConvocatoria, areasTematicas, dirigidoA, fechaCierre, paisRegion, enlace)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (item.get('nombreConvocatoria'), item.get('areasTematicas'), item.get('dirigidoA'), item.get('fechaCierre'), item.get('paisRegion'), item.get('enlace')))
            
        conn.commit()
        cur.close()
        conn.close()
        
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/vigentes")
def get_saved_grants():
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM grants WHERE is_archived = FALSE ORDER BY created_at DESC;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/grants/{{grant_id}}/archive")
def archive_grant(grant_id: int):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE grants SET is_archived = TRUE WHERE id = %s", (grant_id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "message": "Convocatoria archivada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
