import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Azure Configuration
    AZURE_CONNECTION_STRING: str = os.environ.get("AZURE_CONNECTION_STRING")
    BLOB_CONTAINER_INPUT: str = "raw-videos"
    BLOB_CONTAINER_OUTPUT: str = "processed-videos"
    QUEUE_NAME: str = "video-processing-queue"
    
    # AI Configuration
    MODEL_NAME: str = "facebook/detr-resnet-50"
    
    class Config:
        env_file = ".env"

settings = Settings()