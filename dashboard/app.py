import streamlit as st
import requests
import time
import json
import os
import pandas as pd
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

# --- CONFIGURATION ---
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# UNIFIED VARIABLE NAME
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
# FIX: Read from Env (Docker) or default to Localhost
API_URL = os.getenv("API_URL", "http://localhost:8000")
CONTAINER_OUTPUT = "processed-videos"

st.set_page_config(page_title="CattleCounter Ops Center", page_icon="🐮", layout="wide")

# --- UTILS ---
class ProgressReader:
    def __init__(self, file_obj, callback):
        self.file = file_obj
        self.callback = callback
        self.total_size = file_obj.size
        self.bytes_read = 0

    def read(self, size=-1):
        data = self.file.read(size)
        if not data: return b""
        self.bytes_read += len(data)
        if self.total_size > 0: self.callback(self.bytes_read, self.total_size)
        return data

@st.cache_resource
def get_blob_service():
    if not AZURE_STORAGE_CONNECTION_STRING: return None
    return BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

def get_job_status(blob_name):
    client = get_blob_service()
    if not client: return None
    
    base_name = os.path.splitext(blob_name)[0]
    status_filename = f"{base_name}_status.json"
    
    blob_client = client.get_blob_client(container=CONTAINER_OUTPUT, blob=status_filename)
    try:
        if blob_client.exists():
            return json.loads(blob_client.download_blob().readall())
    except: pass
    return None

def get_final_result(blob_name):
    client = get_blob_service()
    base_name = os.path.splitext(blob_name)[0]
    json_filename = f"{base_name}.json"
    
    blob_client = client.get_blob_client(container=CONTAINER_OUTPUT, blob=json_filename)
    try:
        return json.loads(blob_client.download_blob().readall())
    except: return None

# --- UI LAYOUT ---

st.title("🐮 CattleCounter: Aerial Livestock Analytics")
st.markdown("Upload drone footage to perform automated cattle counting using **Computer Vision (Transformers)**.")

with st.sidebar:
    st.header("System Status")
    api_status = "🔴 Offline"
    try:
        if requests.get(f"{API_URL}/", timeout=1).status_code == 200: api_status = "🟢 Online"
    except: pass
    st.metric("API Connection", api_status)
    
    if "job_history" not in st.session_state: st.session_state.job_history = []
    if st.session_state.job_history:
        st.subheader("Recent Jobs")
        st.dataframe(pd.DataFrame(st.session_state.job_history), hide_index=True)

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("1. New Mission")
    uploaded_file = st.file_uploader("Upload Drone Video (MP4)", type=["mp4", "mov"])
    
    if "uploading" not in st.session_state: st.session_state.uploading = False
    
    launch_btn = st.button("🚀 Launch Analysis", type="primary", disabled=(uploaded_file is None or st.session_state.uploading))

    if launch_btn and uploaded_file:
        st.session_state.uploading = True
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("Initiating streaming upload...")
            
            def update_progress(current, total):
                percent = int((current / total) * 100)
                progress_bar.progress(min(percent, 100))
                
                # UX IMPROVEMENT: Feedback for the user during queue registration
                if current >= total:
                    status_text.text("⏳ Upload complete. Registering job...")
                else:
                    status_text.text(f"Uploading: {min(percent, 100)}% ({round(current/1024/1024, 1)} MB)")

            wrapped_file = ProgressReader(uploaded_file, update_progress)
            files = {'file': (uploaded_file.name, wrapped_file, uploaded_file.type)}
            
            response = requests.post(f"{API_URL}/submit-job", files=files)
            
            if response.status_code == 200:
                data = response.json()
                progress_bar.progress(100)
                status_text.text("✅ Job successfully queued!")
                st.session_state.current_blob_name = data.get("blob_name")
                st.success(f"Job ID: {data['job_id']}")
            else:
                st.error(f"Upload Failed: {response.text}")
        except Exception as e:
            st.error(f"Connection Error: {e}")
        finally:
            st.session_state.uploading = False

    if st.session_state.uploading:
        st.info("💡 To cancel, use the 'Stop' button in the top-right corner.")

with col2:
    st.subheader("2. Real-Time Monitor")
    
    if "current_blob_name" in st.session_state:
        blob_name = st.session_state.current_blob_name
        
        status_box = st.empty()
        process_bar = st.progress(0)
        metrics_box = st.container()

        completed = False
        while not completed:
            status_data = get_job_status(blob_name)
            
            if status_data:
                progress = status_data.get("progress_percent", 0)
                status_msg = status_data.get("status", "pending")
                
                process_bar.progress(progress)
                # UX IMPROVEMENT: Show percentage explicitly
                status_box.info(f"AI Worker Status: **{status_msg.upper()}**  {progress}%")
                
                if status_msg == "completed" or progress == 100:
                    completed = True
                    # st.balloons()
                    st.success("Analysis Complete!")
                    
                    result_json = get_final_result(blob_name)
                    if result_json:
                        job_id_short = result_json.get("job_id", "N/A")[:8]
                        if not any(d['ID'] == job_id_short for d in st.session_state.job_history):
                            st.session_state.job_history.append({
                                "ID": job_id_short,
                                "Count": result_json.get("total_count")
                            })
                        
                        with metrics_box:
                            st.divider()
                            m1, m2, m3 = st.columns(3)
                            m1.metric("Total Cows", result_json.get("total_count"))
                            m2.metric("In Frame", result_json.get("total_in"))
                            m3.metric("Out Frame", result_json.get("total_out"))
                            st.json(result_json)
            else:
                status_box.warning("Queued. Waiting for worker...")
                time.sleep(2)
            
            if not completed:
                time.sleep(2)
    else:
        st.info("Upload a video to start monitoring.")