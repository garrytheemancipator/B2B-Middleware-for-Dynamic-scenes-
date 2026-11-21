from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, HttpUrl, field_validator
import uuid
import os
import jwt
from typing import List, Dict
import httpx
from dotenv import load_dotenv
from shared_db import get_db_connection

load_dotenv()

app = FastAPI()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable not set")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Mock storage for scenes (keeping in-memory for now)
scenes: Dict[uuid.UUID, dict] = {}

class Scene(BaseModel):
    name: str
    data_url: HttpUrl

    @field_validator('data_url')
    @classmethod
    def validate_s3_url(cls, v: HttpUrl):
        if v.scheme != 's3':
            raise ValueError('Data URL must use s3:// scheme')
        # In a real scenario, validate against authorized buckets list
        return v

def get_current_tenant(authorization: str = Header(..., alias="Authorization")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("tenant_id", "default")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

@app.get("/v1/scenes")
async def list_scenes(tenant_id: str = Depends(get_current_tenant)):
    return list(scenes.values())

@app.post("/v1/scenes")
async def create_scene(scene: Scene, tenant_id: str = Depends(get_current_tenant)):
    scene_id = uuid.uuid4()
    scenes[scene_id] = {"id": scene_id, **scene.model_dump()}
    return {"id": scene_id, "status": "CREATED"}

@app.get("/v1/tasks/{task_id}")
async def get_task_status(task_id: str, tenant_id: str = Depends(get_current_tenant)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(task)

async def trigger_rendering(task_id: uuid.UUID, scene_id: uuid.UUID, tenant_id: str):
    scene = scenes.get(scene_id)
    if not scene:
        return
        
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("http://localhost:8001/v1/orchestrate", json={
                "task_id": str(task_id),
                "tenant_id": tenant_id,
                "rendering_technique": "3DGS",
                "scene_data_url": str(scene["data_url"])
            })
            
            status = "QUEUED" if response.status_code == 200 else "FAILED"
            
            # Update DB
            conn = get_db_connection()
            conn.execute("INSERT OR REPLACE INTO tasks (task_id, tenant_id, status, scene_data_url) VALUES (?, ?, ?, ?)",
                         (str(task_id), tenant_id, status, str(scene["data_url"])))
            conn.commit()
            conn.close()
            
        except Exception as e:
            conn = get_db_connection()
            conn.execute("INSERT OR REPLACE INTO tasks (task_id, tenant_id, status, scene_data_url) VALUES (?, ?, ?, ?)",
                         (str(task_id), tenant_id, "FAILED", str(scene["data_url"])))
            conn.commit()
            conn.close()
