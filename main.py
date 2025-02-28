from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import httpx
from datetime import datetime, timedelta
import asyncio
from typing import Optional
from pydantic import BaseModel
import os

app = FastAPI()

# CORS configuration
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RestDB Configuration
RESTDB_URL = "https://andaimeconami-0ccc.restdb.io"
RESTDB_KEY = "35a977b68e9beccc345bc1c7a442b99ca2861"
HEADERS = {
    "x-apikey": RESTDB_KEY,
    "Content-Type": "application/json"
}

# WhatsApp API Configuration
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "seu_token_aqui")
WHATSAPP_URL = "https://graph.facebook.com/v17.0/YOUR_PHONE_NUMBER_ID/messages"
WHATSAPP_HEADERS = {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    "Content-Type": "application/json"
}

class Andaime(BaseModel):
    area: str
    subArea: str
    startDate: str
    estimatedEndDate: str
    leaderName: str
    executorName: str
    leaderPhone: str
    executorPhone: str
    status: str = "active"

async def enviar_mensagem_whatsapp(phone: str, message: str):
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": message}
        }
        async with httpx.AsyncClient() as client:
            await client.post(WHATSAPP_URL, headers=WHATSAPP_HEADERS, json=payload)
    except Exception as e:
        print(f"Erro ao enviar mensagem WhatsApp: {str(e)}")

async def verificar_andaimes_expirados():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{RESTDB_URL}/rest/scaffolds", headers=HEADERS)
                andaimes = response.json()
                now = datetime.now()

                for andaime in andaimes:
                    end_date = datetime.fromisoformat(andaime['estimatedEndDate'].replace('Z', '+00:00'))
                    days_expired = (now - end_date).days

                    if days_expired == 0:
                        mensagem = (
                            f"ATENÇÃO: Andaime expirado!\n"
                            f"Área: {andaime['area']}\n"
                            f"Subárea: {andaime['subArea']}\n"
                            f"Data de início: {andaime['startDate']}\n"
                            f"Data de término: {andaime['estimatedEndDate']}\n"
                            f"Por favor, atualize a liberação do andaime imediatamente."
                        )
                        
                        await enviar_mensagem_whatsapp(andaime['leaderPhone'], mensagem)
                        await enviar_mensagem_whatsapp(andaime['executorPhone'], mensagem)

                    elif days_expired > 3:
                        await client.delete(
                            f"{RESTDB_URL}/rest/scaffolds/{andaime['_id']}",
                            headers=HEADERS
                        )

            await asyncio.sleep(24 * 60 * 60)
        except Exception as e:
            print(f"Erro na verificação de andaimes: {str(e)}")
            await asyncio.sleep(60)

@app.get("/andaimes")
async def get_andaimes():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{RESTDB_URL}/rest/scaffolds",
                headers=HEADERS
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Falha ao buscar andaimes")
            
            andaimes = response.json()
            now = datetime.now()
            
            for andaime in andaimes:
                end_date = datetime.fromisoformat(andaime['estimatedEndDate'].replace('Z', '+00:00'))
                days_until = (end_date - now).days
                andaime['diasAteExpiracao'] = max(0, days_until)
                andaime['status'] = 'expirado' if days_until <= 0 else 'ativo'
            
            return andaimes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/andaimes")
async def create_andaime(andaime: Andaime):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RESTDB_URL}/rest/scaffolds",
                headers=HEADERS,
                json=andaime.dict()
            )
            
            if response.status_code != 201:
                raise HTTPException(status_code=500, detail="Falha ao criar andaime")
            
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(verificar_andaimes_expirados())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
