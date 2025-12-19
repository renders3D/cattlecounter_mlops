import streamlit as st
import requests
import time
import json
import os
import pandas as pd
import plotly.express as px
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
API_URL = os.getenv("CLOUD_API_URL", "http://localhost:8000")
CONTAINER_OUTPUT = "processed-videos"

st.set_page_config(page_title="CattleCounter Ops Center", page_icon="🐮", layout="wide")

# --- CUSTOM CSS FOR BLUE THEME ---
# st.markdown("""
#     <style>
#     /* Change Tab Selection Color to Azure Blue */
#     .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
#         font-size: 1.1rem;
#     }
#     .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] div {
#         background-color: transparent !important;
#         border-top-color: #0078D4 !important;
#     }
#     .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] p {
#         color: #0078D4 !important;
#         font-weight: bold;
#     }
#     /* Customize Primary Button to Blue */
#     div.stButton > button:first-child {
#         background-color: #0078D4;
#         color: white;
#         border: none;
#     }
#     div.stButton > button:first-child:hover {
#         background-color: #005a9e;
#         color: white;
#     }
#     </style>
# """, unsafe_allow_html=True)

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

def get_all_results():
    """Fetches all JSON results for observability"""
    client = get_blob_service()
    if not client: return []
    container_client = client.get_container_client(CONTAINER_OUTPUT)
    results = []
    blobs = container_client.list_blobs()
    for blob in blobs:
        if blob.name.endswith(".json") and not blob.name.endswith("_status.json"):
            try:
                data = json.loads(container_client.download_blob(blob.name).readall())
                data['timestamp'] = blob.last_modified
                # Store base filename to find video later
                data['base_filename'] = blob.name.replace(".json", "")
                results.append(data)
            except: pass
    return results

def download_video_bytes(base_filename):
    """Try to find and download the video associated with a result"""
    client = get_blob_service()
    container_client = client.get_container_client(CONTAINER_OUTPUT)
    # Try common extensions
    for ext in [".mp4", ".mov", ".avi"]:
        video_name = f"{base_filename}{ext}"
        blob_client = container_client.get_blob_client(video_name)
        if blob_client.exists():
            return blob_client.download_blob().readall(), video_name
    return None, None

# --- UI LAYOUT ---

st.title("🐮 CattleCounter: Aerial Livestock Analytics")

# Navigation Tabs
tab_monitor, tab_analytics = st.tabs(["🚀 Mission Control", "📊 Observability & Insights"])

# Sidebar Status
with st.sidebar:
    st.header("System Status")
    api_status = "🔴 Offline"
    try:
        if requests.get(f"{API_URL}/", timeout=2).status_code == 200: 
            api_status = "🟢 Online (Cloud)"
    except: pass
    st.metric("API Connection", api_status)
    st.caption(f"Endpoint: {API_URL}")
    st.divider()
    if st.button("Clear Cache"): st.cache_resource.clear()

# --- TAB 1: MISSION CONTROL ---
with tab_monitor:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("1. New Mission")
        uploaded_file = st.file_uploader("Upload Drone Video", type=["mp4", "mov"])
        
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
                    st.success(f"Job ID: {data['job_id'][:8]}...")
                else:
                    st.error(f"Upload Failed: {response.text}")
            except Exception as e: st.error(f"Connection Error: {e}")
            finally: st.session_state.uploading = False

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
                    prog = status_data.get("progress_percent", 0)
                    msg = status_data.get("status", "pending")
                    process_bar.progress(prog)
                    status_box.info(f"AI Worker Status: **{msg.upper()}** - {prog}%")
                    
                    if msg == "completed" or prog == 100:
                        completed = True
                        st.balloons()
                        st.success("Analysis Complete!")
                        res = get_final_result(blob_name)
                        if res:
                            with metrics_box:
                                st.divider()
                                m1, m2, m3 = st.columns(3)
                                m1.metric("Total Cows", res.get("total_count"))
                                m2.metric("In Frame", res.get("total_in"))
                                m3.metric("Out Frame", res.get("total_out"))
                                st.json(res)
                else:
                    status_box.warning("Queued. Waiting for Cloud Worker...")
                if not completed: time.sleep(2)
        else:
            st.info("Upload a video to start monitoring.")

# --- TAB 2: OBSERVABILITY & INSIGHTS ---
with tab_analytics:
    st.subheader("📈 Historical Performance & Data Observability")
    
    with st.spinner("Fetching mission logs from Azure..."):
        all_data = get_all_results()
    
    if all_data:
        df = pd.DataFrame(all_data)
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        
        # Row 1: KPIs
        k1, k2, k3 = st.columns(3)
        k1.metric("Missions Flown", len(df))
        k2.metric("Avg Herd Size", round(df['total_count'].mean(), 1))
        k3.metric("Total Cattle Detected", df['total_count'].sum())
        
        st.divider()
        
        # Row 2: Charts
        c1, c2 = st.columns(2)
        with c1:
            daily = df.groupby('date')['total_count'].sum().reset_index()
            fig = px.line(daily, x='date', y='total_count', title="Daily Cattle Count")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig2 = px.pie(values=[df['total_in'].sum(), df['total_out'].sum()], 
                          names=['In', 'Out'], title="Movement Distribution")
            st.plotly_chart(fig2, use_container_width=True)

        # Row 3: Audit Log with Video Player
        st.divider()
        st.write("#### 🎥 Visual Audit Log")
        
        col_list, col_video = st.columns([1, 1])
        
        with col_list:
            st.info("Select a mission to verify the AI count against the video footage.")
            
            # Create a display label for the dropdown
            df['label'] = df.apply(lambda x: f"{x['date']} | ID: {x['job_id'][:6]}... | Count: {x['total_count']}", axis=1)
            
            selected_label = st.selectbox("Select Mission", df['label'])
            
            # Find selected row
            selected_row = df[df['label'] == selected_label].iloc[0]
            st.json({
                "Job ID": selected_row['job_id'],
                "Date": str(selected_row['date']),
                "Total Count": selected_row['total_count']
            })

        with col_video:
            if st.button("▶️ Load Processed Video"):
                with st.spinner("Downloading video stream from Azure..."):
                    video_bytes, vid_name = download_video_bytes(selected_row['base_filename'])
                    if video_bytes:
                        st.video(video_bytes)
                        st.caption(f"Playing: {vid_name}")
                        st.success("Ready for visual verification.")
                    else:
                        st.error("Video file not found in storage (might be expired or deleted).")

    else:
        st.warning("No historical missions found.")