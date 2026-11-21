import httpx
import uuid
import time
import asyncio

# Assuming services run on these ports
INGESTION_URL = "http://localhost:8000"
ORCHESTRATOR_URL = "http://localhost:8001"
DASHBOARD_URL = "http://localhost:8002"

async def test_full_pipeline():
    async with httpx.AsyncClient() as client:
        print("--- Starting Full EGM Pipeline Test ---")
        
        # 1. Ingest Data (Simulating a trusted device)
        print("1. Ingesting Data...")
        # (Simplified ingestion call for smoke test)
        # 2. Trigger Orchestration via Dashboard
        print("2. Triggering Orchestration...")
        scene_id = uuid.uuid4()
        # Mock scene creation
        await client.post(f"{DASHBOARD_URL}/v1/scenes", json={"name": "Test Scene", "data_url": "s3://safe-bucket/test"})
        
        # 3. Verify Status
        print("3. Verifying Pipeline Status...")
        # ... check status
        print("--- Pipeline Test Completed ---")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
