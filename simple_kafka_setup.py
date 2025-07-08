#!/usr/bin/env python3
"""
Simple Kafka Setup - Quick integration for your existing project
Uses .env configuration automatically
"""

import os
from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError
import logging
from dotenv import load_dotenv
    
# Load environment variables from .env

load_dotenv()
    
logger = logging.getLogger(__name__)

def get_kafka_config():
    """Get Kafka configuration from .env with fallbacks"""
    config = {
        'bootstrap_servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
        'topic_audio': os.getenv('KAFKA_TOPIC_AUDIO', 'audio-transcription'),
        'consumer_group': os.getenv('KAFKA_CONSUMER_GROUP', 'transcription-workers')
    }
    
    
    print(f"✅ Using configuration from .env:")
    print(f"   Kafka Servers: {config['bootstrap_servers']}")
    print(f"   Topic Name: {config['topic_audio']}")
    
    return config

def ensure_kafka_topic(topic_name=None, bootstrap_servers=None, 
                       num_partitions=1, replication_factor=1):
    """
    Simple function to ensure a Kafka topic exists
    Uses .env configuration if parameters not provided
    Returns True if topic exists or was created successfully
    """
    # Get config from .env if not provided
    config = get_kafka_config()
    
    if topic_name is None:
        topic_name = config['topic_audio']
    
    if bootstrap_servers is None:
        bootstrap_servers = config['bootstrap_servers']
    
    try:
        # Create admin client
        admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id="setup_client"
        )
        
        # Check if topic already exists
        existing_topics = admin_client.list_topics()
        if topic_name in existing_topics:
            logger.info(f"✅ Kafka topic '{topic_name}' already exists")
            admin_client.close()
            return True
        
        # Create topic
        topic = NewTopic(
            name=topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
            topic_configs={
                'cleanup.policy': 'delete',
                'retention.ms': '86400000',  # 1 day retention
                'compression.type': 'snappy'
            }
        )
        
        # Execute creation
        result = admin_client.create_topics([topic])
        
        # Wait for result
        for topic_name, future in result.items():
            try:
                future.result(timeout=10)
                logger.info(f"✅ Kafka topic '{topic_name}' created successfully")
                admin_client.close()
                return True
            except TopicAlreadyExistsError:
                logger.info(f"✅ Kafka topic '{topic_name}' already exists")
                admin_client.close()
                return True
            except Exception as e:
                logger.error(f"❌ Failed to create topic '{topic_name}': {e}")
                admin_client.close()
                return False
                
    except Exception as e:
        logger.error(f"❌ Kafka connection failed: {e}")
        print(f"   Make sure Kafka is running at: {bootstrap_servers}")
        return False

# Quick setup function for your project
def setup_audio_transcription_kafka():
    """Setup function specifically for your audio transcription project using .env config"""
    config = get_kafka_config()
    
    return ensure_kafka_topic(
        topic_name=config['topic_audio'],
        bootstrap_servers=config['bootstrap_servers'],
        num_partitions=1,
        replication_factor=1
    )

# Usage examples:
if __name__ == "__main__":
    print("🎵 Audio Transcription Kafka Setup")
    print("=" * 40)
    
    # Simple usage with .env configuration
    success = setup_audio_transcription_kafka()
    
    if success:
        print("\n🎉 Kafka setup completed successfully!")
        print("   Your audio transcription service is ready to use.")
    else:
        print("\n❌ Kafka setup failed.")
        print("   Please check:")
        print("   1. Kafka server is running")
        print("   2. KAFKA_BOOTSTRAP_SERVERS in .env is correct")
        print("   3. Network connectivity to Kafka")
        exit(1)