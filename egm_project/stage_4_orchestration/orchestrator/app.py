import uuid
import asyncio
import os
import redis
import hmac
import hashlib
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Depends
from pydantic import BaseModel, HttpUrl, field_validator
from shared_db import get_db_connection

load_dotenv()

app = FastAPI()
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable not set")

class GPUManager:
    def check_availability(self) -> bool:
        return True

    def schedule(self, task_id: uuid.UUID):
        pass

class OrchestratorService:
    def __init__(self):
        self.redis = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
        # Quotas are managed in Redis
        # self.tenant_quotas = {"default": 5, "tenant1": 10}
        self.gpu_manager = GPUManager()

    def try_acquire_slot(self, tenant_id: str) -> bool:
        if not self.gpu_manager.check_availability():
            return False
        
        # Get quota from Redis, default to 5
        quota = int(self.redis.get(f"quota:{tenant_id}") or self.redis.get("quota:default") or 5)
        active_key = f"active_tasks:{tenant_id}"
        
        current_active = self.redis.get(active_key)
        current_active = int(current_active) if current_active else 0
            
        if current_active < quota:
            self.redis.incr(active_key)
            return True
        return False

    def decrement_tasks(self, tenant_id: str):
        active_key = f"active_tasks:{tenant_id}"
        if int(self.redis.get(active_key) or 0) > 0:
            self.redis.decr(active_key)

service = OrchestratorService()

class RenderingTask(BaseModel):
    task_id: uuid.UUID
    tenant_id: str
    rendering_technique: str
    scene_data_url: HttpUrl

    @field_validator('scene_data_url')
    @classmethod
    def validate_s3_url(cls, v: HttpUrl):
        if v.scheme != 's3':
            raise ValueError('Data URL must use s3:// scheme')
        return v

def verify_signature(request_body: RenderingTask, signature: str = Header(..., alias="X-Signature")):
    msg = str(request_body.model_dump()).encode()
    expected = hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    return True

@app.post("/v1/orchestrate", dependencies=[Depends(verify_signature)])
async def orchestrate(task: RenderingTask, background_tasks: BackgroundTasks):
    if not service.try_acquire_slot(task.tenant_id):
        raise HTTPException(status_code=429, detail="Tenant resource quota or GPU capacity exceeded")
    
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO tasks (task_id, tenant_id, status, scene_data_url) VALUES (?, ?, ?, ?)",
                 (str(task.task_id), task.tenant_id, "QUEUED", str(task.scene_data_url)))
    conn.commit()
    conn.close()

    service.gpu_manager.schedule(task.task_id)
    background_tasks.add_task(run_rendering, task)
    
    return {"status": "QUEUED", "task_id": task.task_id}

async def run_rendering(task: RenderingTask):
    try:
        await asyncio.sleep(10)
        conn = get_db_connection()
        conn.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("COMPLETED", str(task.task_id)))
        conn.commit()
        conn.close()
    except Exception:
        conn = get_db_connection()
        conn.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("FAILED", str(task.task_id)))
        conn.commit()
        conn.close()
    finally:
        service.decrement_tasks(task.tenant_id)
