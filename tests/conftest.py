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
    
    @classmethod
    def ensure_kafka_topic(cls):
        """Create Kafka topic if it doesn't exist"""
        try:
            from kafka import KafkaAdminClient
            from kafka.admin import NewTopic
            from kafka.errors import TopicAlreadyExistsError
            
            # Create admin client
            admin_client = KafkaAdminClient(
                bootstrap_servers=cls.KAFKA_BOOTSTRAP_SERVERS,
                client_id="setup_client",
                request_timeout_ms=10000
            )
            
            # Check if topic exists
            existing_topics = admin_client.list_topics()
            if cls.KAFKA_TOPIC_AUDIO in existing_topics:
                print(f"✅ Kafka topic '{cls.KAFKA_TOPIC_AUDIO}' already exists")
                admin_client.close()
                return True
            
            # Create topic
            topic = NewTopic(
                name=cls.KAFKA_TOPIC_AUDIO,
                num_partitions=1,
                replication_factor=1,
                topic_configs={
                    'cleanup.policy': 'delete',
                    'retention.ms': '86400000'  # 1 day
                }
            )
            
            # Execute creation
            result = admin_client.create_topics([topic])
            for topic_name, future in result.items():
                try:
                    future.result(timeout=10)
                    print(f"✅ Kafka topic '{topic_name}' created successfully")
                    admin_client.close()
                    return True
                except TopicAlreadyExistsError:
                    print(f"✅ Kafka topic '{topic_name}' already exists")
                    admin_client.close()
                    return True
                except Exception as e:
                    print(f"❌ Failed to create topic '{topic_name}': {e}")
                    admin_client.close()
                    return False
                    
        except ImportError:
            print("⚠️ kafka-python not installed. Install with: pip install kafka-python")
            return False
        except Exception as e:
            print(f"❌ Kafka setup failed: {e}")
            print("   Make sure Kafka is running and accessible")
            return False
    
    @classmethod
    def setup_all(cls):
        """Setup all required infrastructure"""
        print("🚀 Setting up infrastructure...")
        
        # Setup upload folder
        cls.ensure_upload_folder()
        
        # Setup Kafka topic
        kafka_success = cls.ensure_kafka_topic()
        
        if kafka_success:
            print("✅ All infrastructure setup completed!")
            return True
        else:
            print("⚠️ Infrastructure setup completed with warnings")
            return False