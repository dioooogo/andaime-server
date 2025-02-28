from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import httpx
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

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

class Scaffold(BaseModel):
    area: str
    subArea: str
    startDate: str
    estimatedEndDate: str
    leaderName: str
    executorName: str
    leaderPhone: str
    executorPhone: str
    status: str = "active"

@app.get("/scaffolds")
async def get_scaffolds():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{RESTDB_URL}/rest/scaffolds",
                headers=HEADERS
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to fetch scaffolds")
            
            scaffolds = response.json()
            now = datetime.now()
            
            # Process scaffolds to calculate days until expiration
            for scaffold in scaffolds:
                end_date = datetime.fromisoformat(scaffold['estimatedEndDate'].replace('Z', '+00:00'))
                days_until = (end_date - now).days
                scaffold['daysUntilExpiration'] = max(0, days_until)
                scaffold['status'] = 'expired' if days_until <= 0 else 'active'
            
            return scaffolds
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scaffolds")
async def create_scaffold(scaffold: Scaffold):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RESTDB_URL}/rest/scaffolds",
                headers=HEADERS,
                json=scaffold.dict()
            )
            
            if response.status_code != 201:
                raise HTTPException(status_code=500, detail="Failed to create scaffold")
            
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/scaffolds/{scaffold_id}")
async def update_scaffold(scaffold_id: str, status: str, newEndDate: Optional[str] = None):
    try:
        update_data = {"status": status}
        if newEndDate:
            update_data["estimatedEndDate"] = newEndDate

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{RESTDB_URL}/rest/scaffolds/{scaffold_id}",
                headers=HEADERS,
                json=update_data
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to update scaffold")
            
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/scaffolds/{scaffold_id}")
async def delete_scaffold(scaffold_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{RESTDB_URL}/rest/scaffolds/{scaffold_id}",
                headers=HEADERS
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to delete scaffold")
            
            return {"message": "Scaffold deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
