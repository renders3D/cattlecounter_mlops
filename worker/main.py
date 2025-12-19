import time
import json
import os
from core.azure_client import azure_client
from core.config import settings
from ml_engine.counter import CowCounterEngine

def run_worker():
    print("👷 Worker started. Waiting for jobs...")
    
    # Initialize Engine (Loads model into memory once)
    engine = CowCounterEngine()
    
    while True:
        messages = azure_client.get_messages()
        
        for msg in messages:
            try:
                print(f"📨 Processing message ID: {msg.id}")
                content = json.loads(msg.content)
                job_id = content['job_id']
                blob_name = content['filename']
                
                local_input = f"temp_{blob_name}"
                local_output = f"processed_{blob_name}"
                
                # Naming Logic: video.mp4 -> video_status.json
                base_name = os.path.splitext(blob_name)[0]
                status_blob_name = f"{base_name}_status.json"

                # Define Progress Callback
                def report_progress(percent):
                    status_data = {
                        "job_id": job_id,
                        "status": "processing",
                        "progress_percent": percent
                    }
                    try:
                        azure_client.upload_file(
                            json.dumps(status_data),
                            status_blob_name,
                            settings.BLOB_CONTAINER_OUTPUT
                        )
                        print(f"   [State Update] {percent}% uploaded to {status_blob_name}")
                    except Exception as upload_err:
                        print(f"⚠️ Failed to update progress: {upload_err}")

                print(f"⬇️ Downloading {blob_name}...")
                report_progress(0)
                
                azure_client.download_file(blob_name, settings.BLOB_CONTAINER_INPUT, local_input)
                
                print(f"🐮 Analyzing video...")
                stats = engine.process_video(local_input, local_output, progress_callback=report_progress)
                
                print(f"⬆️ Uploading processed result (Streaming)...")
                with open(local_output, "rb") as f:
                    azure_client.upload_file(
                        f, 
                        blob_name, 
                        settings.BLOB_CONTAINER_OUTPUT
                    )
                
                # Upload Final JSON Stats
                json_name = f"{base_name}.json"
                stats['job_id'] = job_id
                stats['status'] = 'completed'
                stats['progress_percent'] = 100
                
                azure_client.upload_file(
                    json.dumps(stats), 
                    json_name, 
                    settings.BLOB_CONTAINER_OUTPUT
                )
                
                # Mark status as completed
                azure_client.upload_file(
                    json.dumps({"status": "completed", "progress_percent": 100}),
                    status_blob_name,
                    settings.BLOB_CONTAINER_OUTPUT
                )

                # Acknowledge Job (Delete from Queue)
                azure_client.delete_message(msg)
                print(f"✅ Job {job_id} finished successfully. Total Count: {stats['total_count']}")
                
                # Cleanup local files
                if os.path.exists(local_input): os.remove(local_input)
                if os.path.exists(local_output): os.remove(local_output)

            except Exception as e:
                print(f"❌ Error processing job: {e}")
                
        # Poll interval
        time.sleep(5)

if __name__ == "__main__":
    run_worker()