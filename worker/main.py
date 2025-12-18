import time
import json
import os
from core.azure_client import azure_client
from core.config import settings
from ml_engine.counter import CowCounterEngine

def run_worker():
    print("👷 Worker started. Waiting for jobs...")
    
    engine = CowCounterEngine()
    
    while True:
        messages = azure_client.get_messages()
        
        for msg in messages:
            try:
                print(f"📨 Processing message: {msg.id}")
                content = json.loads(msg.content)
                job_id = content['job_id']
                blob_name = content['filename']
                
                local_input = f"temp_{blob_name}"
                local_output = f"processed_{blob_name}"
                
                # STATUS FILE NAME (e.g., uuid_status.json)
                status_blob_name = blob_name.replace(".mp4", "_status.json")

                # Define the callback function
                def report_progress(percent):
                    # Create a small status object
                    status_data = {
                        "job_id": job_id,
                        "status": "processing",
                        "progress_percent": percent
                    }
                    # Upload to Output container (Overwrite enabled)
                    # This is lightweight enough to do periodically
                    try:
                        azure_client.upload_file(
                            json.dumps(status_data),
                            status_blob_name,
                            settings.BLOB_CONTAINER_OUTPUT
                        )
                    except Exception as upload_err:
                        print(f"⚠️ Failed to update progress: {upload_err}")

                print(f"⬇️ Downloading {blob_name}...")
                # Update status to 'downloading'
                report_progress(0)
                
                azure_client.download_file(blob_name, settings.BLOB_CONTAINER_INPUT, local_input)
                
                print(f"🐮 Analyzing video...")
                # PASS THE CALLBACK HERE
                stats = engine.process_video(local_input, local_output, progress_callback=report_progress)
                
                print(f"⬆️ Uploading result...")
                azure_client.upload_file(
                    open(local_output, "rb").read(), 
                    blob_name, 
                    settings.BLOB_CONTAINER_OUTPUT
                )
                
                # Upload Final Metadata
                json_name = blob_name.replace(".mp4", ".json")
                stats['job_id'] = job_id
                stats['status'] = 'completed'
                stats['progress_percent'] = 100
                
                azure_client.upload_file(
                    json.dumps(stats), 
                    json_name, 
                    settings.BLOB_CONTAINER_OUTPUT
                )
                
                # Delete the temp status file (Clean up)
                # Or keep it saying "100%"
                azure_client.upload_file(
                    json.dumps({"status": "completed", "progress_percent": 100}),
                    status_blob_name,
                    settings.BLOB_CONTAINER_OUTPUT
                )

                azure_client.delete_message(msg)
                print(f"✅ Job {job_id} finished. Count: {stats['total_count']}")
                
                if os.path.exists(local_input): os.remove(local_input)
                if os.path.exists(local_output): os.remove(local_output)

            except Exception as e:
                print(f"❌ Error processing job: {e}")
                
        time.sleep(5)

if __name__ == "__main__":
    run_worker()