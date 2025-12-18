from fastapi import FastAPI, UploadFile, File, HTTPException
from core.azure_client import azure_client
from core.config import settings
import uuid
import os
import json
import traceback # Importamos esto para ver el error real

app = FastAPI(title="CattleCounter Cloud API", version="1.0.0")

@app.post("/submit-job")
async def submit_job(file: UploadFile = File(...)):
    print(f"📥 Receiving file: {file.filename}") # Debug 1

    if not file.filename.endswith(('.mp4', '.mov', '.avi')):
        raise HTTPException(status_code=400, detail="Invalid file format")

    job_id = str(uuid.uuid4())
    extension = os.path.splitext(file.filename)[1]
    blob_name = f"{job_id}{extension}"

    try:
        # Debug 2: Verificar configuración antes de subir
        print(f"🔧 Config check - Container: {settings.BLOB_CONTAINER_INPUT}")
        if "DefaultEndpointsProtocol" not in settings.AZURE_CONNECTION_STRING:
             raise ValueError("CRITICAL: AZURE_CONNECTION_STRING is missing or invalid in .env")

        # 1. Upload
        print("⬆️ Attempting upload to Blob Storage...")
        contents = await file.read()
        azure_client.upload_file(contents, blob_name, settings.BLOB_CONTAINER_INPUT)
        print("✅ Upload successful.")

        # 2. Push to Queue
        print("📨 Attempting push to Queue...")
        message_payload = {
            "job_id": job_id,
            "filename": blob_name,
            "status": "pending"
        }
        azure_client.push_to_queue(json.dumps(message_payload))
        print("✅ Queue push successful.")

        return {
            "job_id": job_id,
            "status": "queued",
            "message": "Video uploaded successfully. Processing started."
        }

    except Exception as e:
        # ESTO ES LO IMPORTANTE: Imprimir el error completo en la terminal
        print("❌ ERROR TRACEBACK:")
        traceback.print_exc() 
        # Devolver el detalle del error al cliente (Swagger)
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

@app.get("/")
def health_check():
    return {"status": "API Online", "service": "CattleCounter"}