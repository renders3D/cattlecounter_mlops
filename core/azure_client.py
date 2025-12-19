from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from core.config import settings
import os

class AzureServices:
    def __init__(self):
        # Increased timeouts for slow upload connections
        # connection_timeout: Time to establish connection
        # read_timeout: Time waiting for response
        self.blob_service = BlobServiceClient.from_connection_string(
            settings.AZURE_STORAGE_CONNECTION_STRING,
            connection_timeout=300, 
            read_timeout=300
        )
        self.queue_service = QueueServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
        
        self._init_infrastructure()

    def _init_infrastructure(self):
        # Initialize infrastructure silently to avoid log spam
        try:
            for container in [settings.BLOB_CONTAINER_INPUT, settings.BLOB_CONTAINER_OUTPUT]:
                try:
                    self.blob_service.create_container(container)
                except ResourceExistsError: pass
            
            try:
                self.queue_service.create_queue(settings.QUEUE_NAME)
            except ResourceExistsError: pass
        except Exception:
            pass

    def upload_file(self, data, filename, container):
        blob_client = self.blob_service.get_blob_client(container=container, blob=filename)
        
        # Extended timeouts for large video uploads
        # timeout=3600: 1 hour total allowed operation time
        # max_concurrency=4: Upload 4 chunks in parallel
        blob_client.upload_blob(
            data, 
            overwrite=True, 
            max_concurrency=4, 
            timeout=3600,
            connection_timeout=300
        )
        return blob_client.url

    def download_file(self, filename, container, local_path):
        blob_client = self.blob_service.get_blob_client(container=container, blob=filename)
        with open(local_path, "wb") as f:
            f.write(blob_client.download_blob().readall())

    def push_to_queue(self, message: str):
        try:
            self.queue_service.get_queue_client(settings.QUEUE_NAME).send_message(message)
        except ResourceNotFoundError:
            # Self-healing: Recreate queue if missing
            self.queue_service.create_queue(settings.QUEUE_NAME)
            self.queue_service.get_queue_client(settings.QUEUE_NAME).send_message(message)

    def get_messages(self):
        try:
            # visibility_timeout=900: Hide message for 15 mins to allow long video processing
            return self.queue_service.get_queue_client(settings.QUEUE_NAME).receive_messages(
                messages_per_page=1, visibility_timeout=900
            )
        except:
            return []

    def delete_message(self, message):
        self.queue_service.get_queue_client(settings.QUEUE_NAME).delete_message(message)

azure_client = AzureServices()