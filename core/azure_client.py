from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueServiceClient
from core.config import settings
import os

class AzureServices:
    def __init__(self):
        self.blob_service = BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
        self.queue_service = QueueServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
        
        # Ensure containers and queues exist on startup
        self._init_infrastructure()

    def _init_infrastructure(self):
        try:
            # Create Containers if not exist
            self.blob_service.get_container_client(settings.BLOB_CONTAINER_INPUT).create_container()
            self.blob_service.get_container_client(settings.BLOB_CONTAINER_OUTPUT).create_container()
            # Create Queue if not exist
            self.queue_service.get_queue_client(settings.QUEUE_NAME).create_queue()
        except Exception:
            pass # Ignore if already exists

    def upload_file(self, file_data, filename, container):
        blob_client = self.blob_service.get_blob_client(container=container, blob=filename)
        blob_client.upload_blob(file_data, overwrite=True)
        return blob_client.url

    def download_file(self, filename, container, local_path):
        blob_client = self.blob_service.get_blob_client(container=container, blob=filename)
        with open(local_path, "wb") as f:
            f.write(blob_client.download_blob().readall())

    def push_to_queue(self, message: str):
        queue_client = self.queue_service.get_queue_client(settings.QUEUE_NAME)
        # Encode message to Base64 (Azure standard) is handled by the SDK usually, 
        # but pure strings are safer.
        queue_client.send_message(message)

    def get_messages(self):
        queue_client = self.queue_service.get_queue_client(settings.QUEUE_NAME)
        return queue_client.receive_messages(messages_per_page=1, visibility_timeout=300)

    def delete_message(self, message):
        queue_client = self.queue_service.get_queue_client(settings.QUEUE_NAME)
        queue_client.delete_message(message)

azure_client = AzureServices()