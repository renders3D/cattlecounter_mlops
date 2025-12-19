from fastapi import FastAPI, UploadFile, File, HTTPException
from core.azure_client import azure_client
from core.config import settings
import uuid
import os
import json
import traceback

app = FastAPI(title="CattleCounter Cloud API", version="1.0.0")

@app.post("/submit-job")
async def submit_job(file: UploadFile = File(...)):
    print(f"📥 Receiving file stream: {file.filename}")

    if not file.filename.endswith(('.mp4', '.mov', '.avi')):
        raise HTTPException(status_code=400, detail="Invalid file format")

    job_id = str(uuid.uuid4())
    extension = os.path.splitext(file.filename)[1]
    blob_name = f"{job_id}{extension}"

    try:
        # 1. Upload (STREAMING)
        print("⬆️ Streaming to Blob Storage (Chunked Upload)...")
        
        # Passing the file object directly for memory-efficient streaming
        azure_client.upload_file(file.file, blob_name, settings.BLOB_CONTAINER_INPUT)
        
        print("✅ Upload successful.")

        # 2. Push to Queue
        message_payload = {
            "job_id": job_id,
            "filename": blob_name,
            "status": "pending"
        }
        azure_client.push_to_queue(json.dumps(message_payload))
        print("✅ Job pushed to Queue.")

        return {
            "job_id": job_id,
            "blob_name": blob_name,
            "status": "queued",
            "message": "Video uploaded successfully. Job queued."
        }

    except Exception as e:
        print("❌ ERROR TRACEBACK:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

@app.get("/")
def health_check():
    return {"status": "API Online", "service": "CattleCounter"}