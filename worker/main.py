import time
import json
import os
from core.azure_client import azure_client
from core.config import settings
from ml_engine.counter import CowCounterEngine

def run_worker():
    print("👷 Worker started. Waiting for jobs...")
    
    # Initialize Engine once (so we don't reload model per video)
    engine = CowCounterEngine()
    
    while True:
        # 1. Poll Queue
        messages = azure_client.get_messages()
        
        for msg in messages:
            try:
                print(f"📨 Processing message: {msg.id}")
                content = json.loads(msg.content)
                job_id = content['job_id']
                blob_name = content['filename']
                
                # 2. Download Video
                local_input = f"temp_{blob_name}"
                local_output = f"processed_{blob_name}"
                
                print(f"⬇️ Downloading {blob_name}...")
                azure_client.download_file(blob_name, settings.BLOB_CONTAINER_INPUT, local_input)
                
                # 3. Run Inference
                print(f"🐮 Analyzing video...")
                stats = engine.process_video(local_input, local_output)
                
                # 4. Upload Result
                print(f"⬆️ Uploading result...")
                azure_client.upload_file(
                    open(local_output, "rb").read(), 
                    blob_name, 
                    settings.BLOB_CONTAINER_OUTPUT
                )
                
                # 5. Upload Metadata (JSON stats)
                json_name = blob_name.replace(".mp4", ".json")
                stats['job_id'] = job_id
                stats['status'] = 'completed'
                azure_client.upload_file(
                    json.dumps(stats), 
                    json_name, 
                    settings.BLOB_CONTAINER_OUTPUT
                )
                
                # 6. Delete Message (Ack)
                azure_client.delete_message(msg)
                print(f"✅ Job {job_id} finished. Count: {stats['total_count']}")
                
                # Cleanup
                if os.path.exists(local_input): os.remove(local_input)
                if os.path.exists(local_output): os.remove(local_output)

            except Exception as e:
                print(f"❌ Error processing job: {e}")
                # In prod, you might want to move this to a 'poison-queue'
                
        time.sleep(5) # Avoid spamming the API if empty

if __name__ == "__main__":
    run_worker()