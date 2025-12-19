import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Standardized Azure Connection String Name
    AZURE_STORAGE_CONNECTION_STRING: str
    
    # Storage Containers & Queues
    BLOB_CONTAINER_INPUT: str = "raw-videos"
    BLOB_CONTAINER_OUTPUT: str = "processed-videos"
    QUEUE_NAME: str = "video-processing-queue"
    
    # AI Model Configuration
    MODEL_NAME: str = "facebook/detr-resnet-50"
    
    class Config:
        env_file = ".env"
        extra = "ignore" # Ignore extra fields in .env

settings = Settings()