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
                now = datetime.now().date()

                print("\n=== VERIFICAÇÃO DE ANDAIMES ===")
                print(f"Data atual: {now.strftime('%d/%m/%Y')}")
                print(f"Total de andaimes: {len(andaimes)}")

                for andaime in andaimes:
                    end_date = datetime.fromisoformat(andaime['estimatedEndDate'].replace('Z', '+00:00')).date()
                    start_date = datetime.fromisoformat(andaime['startDate'].replace('Z', '+00:00')).date()
                    
                    if start_date > now:
                        print(f"\nAndaime {andaime['area']} ainda não iniciado")
                        print(f"Início programado: {start_date.strftime('%d/%m/%Y')}")
                        continue
                    
                    days_until = (end_date - now).days + 1
                    
                    print(f"\nAndaime: {andaime['area']}")
                    print(f"Status: {andaime['status']}")
                    print(f"Dias restantes: {days_until}")

                    if 0 < days_until <= 3:
                        print(">>> AVISO: Próximo ao vencimento - Enviando notificação")
                        mensagem = (
                            f"ATENÇÃO: Andaime próximo ao vencimento!\n"
                            f"Área: {andaime['area']}\n"
                            f"Subárea: {andaime['subArea']}\n"
                            f"Data de início: {start_date.strftime('%d/%m/%Y')}\n"
                            f"Data de término: {end_date.strftime('%d/%m/%Y')}\n"
                            f"Dias restantes: {days_until}\n"
                            f"Por favor, providencie a renovação da liberação."
                        )
                        await enviar_mensagem_whatsapp(andaime['leaderPhone'], mensagem)
                        await enviar_mensagem_whatsapp(andaime['executorPhone'], mensagem)

                    elif days_until == 0:
                        print(">>> ALERTA: Vence hoje - Enviando notificação")
                        mensagem = (
                            f"ATENÇÃO: Andaime vence HOJE!\n"
                            f"Área: {andaime['area']}\n"
                            f"Subárea: {andaime['subArea']}\n"
                            f"Data de início: {start_date.strftime('%d/%m/%Y')}\n"
                            f"Data de término: {end_date.strftime('%d/%m/%Y')}\n"
                            f"É necessário renovar a liberação IMEDIATAMENTE."
                        )
                        await enviar_mensagem_whatsapp(andaime['leaderPhone'], mensagem)
                        await enviar_mensagem_whatsapp(andaime['executorPhone'], mensagem)
                    
                    elif days_until < 0:
                        if days_until <= -3:
                            print(f">>> EXCLUSÃO: Andaime vencido há {abs(days_until)} dias - Removendo registro")
                            await client.delete(
                                f"{RESTDB_URL}/rest/scaffolds/{andaime['_id']}",
                                headers=HEADERS
                            )
                        else:
                            print(f">>> EXPIRADO: Vencido há {abs(days_until)} dias - Atualizando status")
                            andaime['status'] = 'expired'
                            await client.put(
                                f"{RESTDB_URL}/rest/scaffolds/{andaime['_id']}",
                                headers=HEADERS,
                                json=andaime
                            )

                print("\n=== FIM DA VERIFICAÇÃO ===\n")
            await asyncio.sleep(12 * 60 * 60)  # 12 horas
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
            now = datetime.now().date()  # Usar apenas a data, sem hora
            
            for andaime in andaimes:
                # Ajusta as datas para considerar apenas a data, sem hora
                end_date = datetime.fromisoformat(andaime['estimatedEndDate'].replace('Z', '+00:00')).date()
                start_date = datetime.fromisoformat(andaime['startDate'].replace('Z', '+00:00')).date()
                
                # Se a data de início ainda não chegou
                if start_date > now:
                    # Incluir o primeiro e último dia no cálculo
                    andaime['diasAteExpiracao'] = (end_date - start_date).days + 1
                    andaime['status'] = 'active'
                else:
                    # Incluir o dia atual e o último dia no cálculo
                    days_until = (end_date - now).days + 1
                    andaime['diasAteExpiracao'] = max(0, days_until)
                    # Mantém consistência com o frontend usando 'active' e 'expired'
                    andaime['status'] = 'expired' if days_until <= 0 else 'active'
            
            return andaimes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/andaimes")
async def create_andaime(andaime: Andaime):
    try:
        # Ajusta as datas para manter consistência - usando apenas date()
        start_date = datetime.fromisoformat(andaime.startDate.replace('Z', '+00:00')).date()
        end_date = datetime.fromisoformat(andaime.estimatedEndDate.replace('Z', '+00:00')).date()
        
        # Garante que as datas estão no formato correto
        andaime.startDate = start_date.isoformat()
        andaime.estimatedEndDate = end_date.isoformat()
        
        # Calcula os dias totais e marcos importantes
        dias_totais = (end_date - start_date).days + 1
        dias_ate_notificacao = dias_totais - 3  # Notifica 3 dias antes
        dias_ate_exclusao = dias_totais + 3     # Exclui 3 dias após vencer
        
        print(f"\n=== NOVO ANDAIME REGISTRADO ===")
        print(f"Área: {andaime.area}")
        print(f"Sub-área: {andaime.subArea}")
        print(f"Líder: {andaime.leaderName}")
        print(f"Duração total: {dias_totais} dias")
        print(f"Início: {start_date.strftime('%d/%m/%Y')}")
        print(f"Término: {end_date.strftime('%d/%m/%Y')}")
        print(f"Notificação em: {dias_ate_notificacao} dias")
        print(f"Exclusão em: {dias_ate_exclusao} dias se não renovado")
        print("=============================\n")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RESTDB_URL}/rest/scaffolds",
                headers=HEADERS,
                json=andaime.dict()
            )
            
            if response.status_code != 201:
                raise HTTPException(status_code=500, detail="Falha ao criar andaime")
            
            result = response.json()
            result['diasAteExpiracao'] = dias_totais
            
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    # Iniciar tarefa de verificação de andaimes em background
    asyncio.create_task(verificar_andaimes_expirados())


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
