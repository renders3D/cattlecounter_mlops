from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from core.config import settings
import time
import os

class AzureServices:
    def __init__(self):
        # 1. TIMEOUTS EXTENDIDOS (10 minutos)
        # Esto soluciona el error "Connection aborted / The write operation timed out"
        self.blob_service = BlobServiceClient.from_connection_string(
            settings.AZURE_CONNECTION_STRING,
            connection_timeout=600,
            read_timeout=600
        )
        self.queue_service = QueueServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
        
        # Intentamos reparar la infraestructura al arrancar
        self._init_infrastructure()

    def _init_infrastructure(self):
        print("🔧 Checking Cloud Infrastructure...")
        
        # A. Crear Contenedores de Blob
        for container in [settings.BLOB_CONTAINER_INPUT, settings.BLOB_CONTAINER_OUTPUT]:
            try:
                self.blob_service.create_container(container)
                print(f"   [+] Container '{container}' created.")
            except ResourceExistsError:
                pass # Ya existe, todo bien.
            except Exception as e:
                print(f"   [!] Container warning: {e}")

        # B. Crear Cola (Con reintento anti-zombie)
        queue_client = self.queue_service.get_queue_client(settings.QUEUE_NAME)
        try:
            queue_client.create_queue()
            print(f"   [+] Queue '{settings.QUEUE_NAME}' created.")
        except ResourceExistsError:
            pass # Ya existe
        except Exception as e:
            # Si la cola se está borrando, Azure devuelve error 409. 
            # Avisamos al usuario.
            print(f"   [!] Queue error: {e}")
            print("   ⚠️ Si acabas de borrar la cola manualmente, espera 60 segundos antes de reiniciar.")

    def upload_file(self, file_data, filename, container):
        blob_client = self.blob_service.get_blob_client(container=container, blob=filename)
        
        # TIMEOUTS EN LA SUBIDA
        blob_client.upload_blob(
            file_data, 
            overwrite=True, 
            timeout=600, 
            connection_timeout=600
        )
        return blob_client.url

    def download_file(self, filename, container, local_path):
        blob_client = self.blob_service.get_blob_client(container=container, blob=filename)
        with open(local_path, "wb") as f:
            f.write(blob_client.download_blob().readall())

    def push_to_queue(self, message: str):
        # Auto-healing: Si intentamos enviar y la cola no existe, la creamos al vuelo.
        try:
            queue_client = self.queue_service.get_queue_client(settings.QUEUE_NAME)
            queue_client.send_message(message)
        except ResourceNotFoundError:
            print(f"⚠️ Queue missing. Recreating '{settings.QUEUE_NAME}'...")
            self.queue_service.create_queue(settings.QUEUE_NAME)
            # Reintentar envío
            self.queue_service.get_queue_client(settings.QUEUE_NAME).send_message(message)

    def get_messages(self):
        # Auto-healing en lectura
        try:
            queue_client = self.queue_service.get_queue_client(settings.QUEUE_NAME)
            # Visibility timeout 15 min (900s) para dar tiempo al video largo
            return queue_client.receive_messages(messages_per_page=1, visibility_timeout=900)
        except ResourceNotFoundError:
            # Si la cola no existe, devolvemos lista vacía y la creamos para la próxima
            print("⚠️ Queue not found during polling. Attempting recreation...")
            try:
                self.queue_service.create_queue(settings.QUEUE_NAME)
            except: 
                pass
            return []

    def delete_message(self, message):
        queue_client = self.queue_service.get_queue_client(settings.QUEUE_NAME)
        queue_client.delete_message(message)

azure_client = AzureServices()