from fastapi import FastAPI, UploadFile, File, HTTPException
from core.azure_client import azure_client
from core.config import settings
import uuid
import os
import json

app = FastAPI(title="CattleCounter Cloud API", version="1.0.0")

@app.post("/submit-job")
async def submit_job(file: UploadFile = File(...)):
    """
    1. Upload video to 'raw-videos' container.
    2. Push a message to the Queue with the Job ID.
    """
    if not file.filename.endswith(('.mp4', '.mov', '.avi')):
        raise HTTPException(status_code=400, detail="Invalid file format")

    # Generate unique Job ID
    job_id = str(uuid.uuid4())
    extension = os.path.splitext(file.filename)[1]
    blob_name = f"{job_id}{extension}"

    try:
        # 1. Upload to Blob
        contents = await file.read()
        azure_client.upload_file(contents, blob_name, settings.BLOB_CONTAINER_INPUT)

        # 2. Push to Queue
        # We send a JSON string with the job details
        message_payload = {
            "job_id": job_id,
            "filename": blob_name,
            "status": "pending"
        }
        azure_client.push_to_queue(json.dumps(message_payload))

        return {
            "job_id": job_id,
            "status": "queued",
            "message": "Video uploaded successfully. Processing started."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "API Online", "service": "CattleCounter"}