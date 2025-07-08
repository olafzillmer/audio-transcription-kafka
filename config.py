import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Shared configuration for Audio-Gateway and Transcription-Service"""
    
    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    KAFKA_TOPIC_AUDIO = os.getenv('KAFKA_TOPIC_AUDIO', 'audio-transcription')
    KAFKA_CONSUMER_GROUP = os.getenv('KAFKA_CONSUMER_GROUP', 'transcription-workers')
    
    # File Handling
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/tmp/audio')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 100 * 1024 * 1024))  # 100MB
    
    # Audio-Gateway
    API_KEY = os.getenv('API_KEY', 'your-secret-api-key')
    GATEWAY_HOST = os.getenv('GATEWAY_HOST', '127.0.0.1')
    GATEWAY_PORT = int(os.getenv('GATEWAY_PORT', 5000))
    
    # Transcription-Service  
    WEBSOCKET_HOST = os.getenv('WEBSOCKET_HOST', '127.0.0.1')
    WEBSOCKET_PORT = int(os.getenv('WEBSOCKET_PORT', 8765))
    
    # AI Model Configuration
    GPU_DEVICE = os.getenv('GPU_DEVICE', 'cpu')
    MODEL_ID = os.getenv('MODEL_ID', 'openai/whisper-small')
    
    @classmethod
    def ensure_upload_folder(cls):
        """Create upload folder if it doesn't exist"""
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)