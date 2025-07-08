#!/usr/bin/env python3
"""
Kafka Topic Creator - Python Script
Creates Kafka topics programmatically using configuration from .env file
"""

import sys
import time
import subprocess
import os
from kafka import KafkaAdminClient, KafkaClient
from kafka.admin import ConfigResource, ConfigResourceType, NewTopic
from kafka.errors import TopicAlreadyExistsError, KafkaError
import logging
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_env_config():
    """Load Kafka configuration from .env file with fallbacks"""
    config = {
        'bootstrap_servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
        'topic_audio': os.getenv('KAFKA_TOPIC_AUDIO', 'audio-transcription'),
        'consumer_group': os.getenv('KAFKA_CONSUMER_GROUP', 'transcription-workers')
    }
    
    logger.info(f"📁 Loaded configuration from .env:")
    logger.info(f"   Bootstrap Servers: {config['bootstrap_servers']}")
    logger.info(f"   Audio Topic: {config['topic_audio']}")
    logger.info(f"   Consumer Group: {config['consumer_group']}")
    
    return config

class KafkaTopicManager:
    def __init__(self, bootstrap_servers=None):
        # Use .env config if no servers specified
        if bootstrap_servers is None:
            env_config = get_env_config()
            bootstrap_servers = env_config['bootstrap_servers']
        
        self.bootstrap_servers = bootstrap_servers
        self.admin_client = None
        logger.info(f"🔧 Using Kafka servers: {self.bootstrap_servers}")
    
    def connect(self):
        """Establish connection to Kafka admin client"""
        try:
            self.admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id="topic_creator",
                request_timeout_ms=10000,
                connections_max_idle_ms=30000
            )
            logger.info(f"✅ Connected to Kafka at {self.bootstrap_servers}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Kafka at {self.bootstrap_servers}: {e}")
            logger.error("   Make sure Kafka is running and the server address is correct")
            return False
    
    def topic_exists(self, topic_name):
        """Check if topic already exists"""
        try:
            metadata = self.admin_client.describe_topics([topic_name])
            return topic_name in metadata
        except Exception:
            return False
    
    def list_topics(self):
        """List all existing topics"""
        try:
            metadata = self.admin_client.list_topics()
            return metadata
        except Exception as e:
            logger.error(f"Failed to list topics: {e}")
            return []
    
    def create_topic(self, topic_name, num_partitions=1, replication_factor=1, topic_configs=None):
        """
        Create a Kafka topic using Python kafka-admin
        
        Args:
            topic_name (str): Name of the topic to create
            num_partitions (int): Number of partitions (default: 1)
            replication_factor (int): Replication factor (default: 1)
            topic_configs (dict): Additional topic configurations
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.admin_client:
            logger.error("Not connected to Kafka. Call connect() first.")
            return False
        
        # Check if topic already exists
        if self.topic_exists(topic_name):
            logger.warning(f"📋 Topic '{topic_name}' already exists")
            return True
        
        # Default topic configurations optimized for audio transcription
        if topic_configs is None:
            topic_configs = {
                'cleanup.policy': 'delete',
                'retention.ms': '86400000',  # 1 day (adjust based on your needs)
                'compression.type': 'snappy',  # Good compression for JSON messages
                'max.message.bytes': '104857600'  # 100MB max message size for large audio files
            }
        
        try:
            # Create NewTopic object
            topic = NewTopic(
                name=topic_name,
                num_partitions=num_partitions,
                replication_factor=replication_factor,
                topic_configs=topic_configs
            )
            
            # Create the topic
            result = self.admin_client.create_topics([topic])
            
            # Wait for creation to complete
            for topic_name, future in result.items():
                try:
                    future.result(timeout=10)  # Wait up to 10 seconds
                    logger.info(f"✅ Topic '{topic_name}' created successfully")
                    logger.info(f"   Partitions: {num_partitions}")
                    logger.info(f"   Replication Factor: {replication_factor}")
                    
                    # Verify creation
                    if self.topic_exists(topic_name):
                        logger.info(f"✅ Topic '{topic_name}' verified to exist")
                        return True
                    else:
                        logger.warning(f"⚠️ Topic '{topic_name}' creation reported success but topic not found")
                        return False
                        
                except TopicAlreadyExistsError:
                    logger.warning(f"📋 Topic '{topic_name}' already exists")
                    return True
                except Exception as e:
                    logger.error(f"❌ Failed to create topic '{topic_name}': {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Failed to create topic '{topic_name}': {e}")
            return False
    
    def delete_topic(self, topic_name):
        """Delete a Kafka topic"""
        if not self.admin_client:
            logger.error("Not connected to Kafka")
            return False
        
        try:
            result = self.admin_client.delete_topics([topic_name])
            for topic, future in result.items():
                future.result(timeout=10)
                logger.info(f"🗑️ Topic '{topic}' deleted successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete topic '{topic_name}': {e}")
            return False
    
    def get_topic_info(self, topic_name):
        """Get detailed information about a topic"""
        try:
            # Get topic metadata
            consumer = self.admin_client
            metadata = consumer.list_consumer_group_offsets(topic_name)
            logger.info(f"Topic '{topic_name}' information retrieved")
            return metadata
        except Exception as e:
            logger.error(f"Failed to get topic info: {e}")
            return None
    
    def close(self):
        """Close the admin client connection"""
        if self.admin_client:
            self.admin_client.close()
            logger.info("Kafka admin client closed")

# Alternative method using subprocess (fallback)
def create_topic_with_cli(topic_name, bootstrap_server=None, 
                         partitions=1, replication_factor=1):
    """
    Create Kafka topic using CLI command via subprocess
    This is a fallback method if kafka-python admin doesn't work
    """
    # Use .env config if no server specified
    if bootstrap_server is None:
        env_config = get_env_config()
        bootstrap_server = env_config['bootstrap_servers']
    
    cmd = [
        "kafka-topics", "--create",
        "--topic", topic_name,
        "--bootstrap-server", bootstrap_server,
        "--partitions", str(partitions),
        "--replication-factor", str(replication_factor)
    ]
    
    try:
        logger.info(f"🔧 Running CLI command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info(f"✅ Topic '{topic_name}' created successfully via CLI")
            return True
        else:
            if "already exists" in result.stderr:
                logger.warning(f"📋 Topic '{topic_name}' already exists")
                return True
            else:
                logger.error(f"❌ CLI command failed: {result.stderr}")
                return False
    except subprocess.TimeoutExpired:
        logger.error("❌ CLI command timed out")
        return False
    except FileNotFoundError:
        logger.error("❌ kafka-topics command not found in PATH")
        logger.error("   Make sure Kafka CLI tools are installed and in PATH")
        return False
    except Exception as e:
        logger.error(f"❌ CLI command failed: {e}")
        return False

# Method using simple kafka client check + CLI
def create_topic_safe(topic_name, bootstrap_server=None, 
                     partitions=1, replication_factor=1, max_retries=3):
    """
    Safe topic creation with fallback methods and retries
    Uses .env configuration if available
    """
    # Use .env config if no server specified
    if bootstrap_server is None:
        env_config = get_env_config()
        bootstrap_server = env_config['bootstrap_servers']
    
    logger.info(f"🚀 Creating topic '{topic_name}' with {partitions} partitions...")
    logger.info(f"🔧 Using Kafka server: {bootstrap_server}")
    
    # Method 1: Try kafka-python admin client
    try:
        manager = KafkaTopicManager(bootstrap_server)
        if manager.connect():
            success = manager.create_topic(
                topic_name, 
                num_partitions=partitions,
                replication_factor=replication_factor
            )
            manager.close()
            if success:
                return True
        logger.warning("⚠️ kafka-python admin method failed, trying CLI fallback...")
    except Exception as e:
        logger.warning(f"⚠️ kafka-python method failed: {e}")
    
    # Method 2: Fallback to CLI
    for attempt in range(max_retries):
        logger.info(f"🔄 CLI attempt {attempt + 1}/{max_retries}")
        if create_topic_with_cli(topic_name, bootstrap_server, partitions, replication_factor):
            return True
        if attempt < max_retries - 1:
            time.sleep(2)  # Wait before retry
    
    logger.error(f"❌ All methods failed to create topic '{topic_name}'")
    return False

# Convenience functions for common use cases
def create_audio_transcription_topic(bootstrap_server=None):
    """Create the standard audio-transcription topic using .env config"""
    env_config = get_env_config()
    
    return create_topic_safe(
        topic_name=env_config['topic_audio'],
        bootstrap_server=bootstrap_server or env_config['bootstrap_servers'],
        partitions=1,
        replication_factor=1
    )

def setup_kafka_topics_for_project(bootstrap_server=None):
    """Setup all necessary Kafka topics for the audio transcription project"""
    env_config = get_env_config()
    
    if bootstrap_server is None:
        bootstrap_server = env_config['bootstrap_servers']
    
    topics_to_create = [
        {
            "name": env_config['topic_audio'],  # Use topic name from .env
            "partitions": 1,
            "replication_factor": 1,
            "description": "Main topic for audio transcription jobs"
        },
        {
            "name": f"{env_config['topic_audio']}-results", 
            "partitions": 1,
            "replication_factor": 1,
            "description": "Optional topic for storing transcription results"
        },
        {
            "name": f"{env_config['topic_audio']}-errors",
            "partitions": 1, 
            "replication_factor": 1,
            "description": "Optional topic for failed transcription jobs (dead letter queue)"
        }
    ]
    
    logger.info(f"🚀 Setting up {len(topics_to_create)} topics for audio transcription project...")
    
    success_count = 0
    for topic_config in topics_to_create:
        logger.info(f"📋 Creating {topic_config['description']}")
        if create_topic_safe(
            topic_name=topic_config["name"],
            bootstrap_server=bootstrap_server,
            partitions=topic_config["partitions"],
            replication_factor=topic_config["replication_factor"]
        ):
            success_count += 1
        else:
            logger.error(f"❌ Failed to create topic: {topic_config['name']}")
    
    logger.info(f"✅ Successfully created {success_count}/{len(topics_to_create)} topics")
    return success_count == len(topics_to_create)

# Main function for command line usage
def main():
    import argparse
    
    # Load environment config for defaults
    env_config = get_env_config()
    
    parser = argparse.ArgumentParser(
        description="Kafka Topic Creator for Audio Transcription (uses .env configuration)"
    )
    parser.add_argument(
        "--topic", 
        default=env_config['topic_audio'], 
        help=f"Topic name to create (default from .env: {env_config['topic_audio']})"
    )
    parser.add_argument(
        "--server", 
        default=env_config['bootstrap_servers'], 
        help=f"Kafka bootstrap server (default from .env: {env_config['bootstrap_servers']})"
    )
    parser.add_argument("--partitions", type=int, default=1, help="Number of partitions")
    parser.add_argument("--replication", type=int, default=1, help="Replication factor")
    parser.add_argument("--setup-all", action="store_true", help="Setup all project topics")
    parser.add_argument("--list", action="store_true", help="List existing topics")
    parser.add_argument("--delete", help="Delete specified topic")
    parser.add_argument("--show-config", action="store_true", help="Show configuration from .env")
    
    args = parser.parse_args()
    
    if args.show_config:
        # Show current configuration
        print("\n📋 Current Configuration:")
        print("=" * 40)
        print(f"Bootstrap Servers: {args.server}")
        print(f"Default Topic: {args.topic}")
        print(f"Consumer Group: {env_config['consumer_group']}")        
        return
    
    if args.list:
        # List topics
        manager = KafkaTopicManager(args.server)
        if manager.connect():
            topics = manager.list_topics()
            print(f"\n📋 Existing topics on {args.server}:")
            print("=" * 40)
            for topic in sorted(topics):
                print(f"  • {topic}")
            manager.close()
        return
    
    if args.delete:
        # Delete topic
        manager = KafkaTopicManager(args.server)
        if manager.connect():
            success = manager.delete_topic(args.delete)
            manager.close()
            sys.exit(0 if success else 1)
        return
    
    if args.setup_all:
        # Setup all project topics
        print(f"\n🚀 Setting up all topics for audio transcription project...")
        print(f"🔧 Using Kafka server: {args.server}")
        success = setup_kafka_topics_for_project(args.server)
        sys.exit(0 if success else 1)
    else:
        # Create single topic
        print(f"\n🚀 Creating single topic: {args.topic}")
        print(f"🔧 Using Kafka server: {args.server}")
        success = create_topic_safe(
            topic_name=args.topic,
            bootstrap_server=args.server,
            partitions=args.partitions,
            replication_factor=args.replication
        )
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
    
    def connect(self):
        """Establish connection to Kafka admin client"""
        try:
            self.admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id="topic_creator",
                request_timeout_ms=10000,
                connections_max_idle_ms=30000
            )
            logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            return False
    
    def topic_exists(self, topic_name):
        """Check if topic already exists"""
        try:
            metadata = self.admin_client.describe_topics([topic_name])
            return topic_name in metadata
        except Exception:
            return False
    
    def list_topics(self):
        """List all existing topics"""
        try:
            metadata = self.admin_client.list_topics()
            return metadata
        except Exception as e:
            logger.error(f"Failed to list topics: {e}")
            return []
    
    def create_topic(self, topic_name, num_partitions=1, replication_factor=1, topic_configs=None):
        """
        Create a Kafka topic using Python kafka-admin
        
        Args:
            topic_name (str): Name of the topic to create
            num_partitions (int): Number of partitions (default: 1)
            replication_factor (int): Replication factor (default: 1)
            topic_configs (dict): Additional topic configurations
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.admin_client:
            logger.error("Not connected to Kafka. Call connect() first.")
            return False
        
        # Check if topic already exists
        if self.topic_exists(topic_name):
            logger.warning(f"Topic '{topic_name}' already exists")
            return True
        
        # Default topic configurations
        if topic_configs is None:
            topic_configs = {
                'cleanup.policy': 'delete',
                'retention.ms': '86400000',  # 1 day
                'compression.type': 'snappy'
            }
        
        try:
            # Create NewTopic object
            topic = NewTopic(
                name=topic_name,
                num_partitions=num_partitions,
                replication_factor=replication_factor,
                topic_configs=topic_configs
            )
            
            # Create the topic
            result = self.admin_client.create_topics([topic])
            
            # Wait for creation to complete
            for topic_name, future in result.items():
                try:
                    future.result(timeout=10)  # Wait up to 10 seconds
                    logger.info(f"✅ Topic '{topic_name}' created successfully")
                    
                    # Verify creation
                    if self.topic_exists(topic_name):
                        logger.info(f"✅ Topic '{topic_name}' verified to exist")
                        return True
                    else:
                        logger.warning(f"⚠️ Topic '{topic_name}' creation reported success but topic not found")
                        return False
                        
                except TopicAlreadyExistsError:
                    logger.warning(f"Topic '{topic_name}' already exists")
                    return True
                except Exception as e:
                    logger.error(f"Failed to create topic '{topic_name}': {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to create topic '{topic_name}': {e}")
            return False
    
    def delete_topic(self, topic_name):
        """Delete a Kafka topic"""
        if not self.admin_client:
            logger.error("Not connected to Kafka")
            return False
        
        try:
            result = self.admin_client.delete_topics([topic_name])
            for topic, future in result.items():
                future.result(timeout=10)
                logger.info(f"Topic '{topic}' deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to delete topic '{topic_name}': {e}")
            return False
    
    def get_topic_info(self, topic_name):
        """Get detailed information about a topic"""
        try:
            # Get topic metadata
            consumer = self.admin_client
            metadata = consumer.list_consumer_group_offsets(topic_name)
            logger.info(f"Topic '{topic_name}' information retrieved")
            return metadata
        except Exception as e:
            logger.error(f"Failed to get topic info: {e}")
            return None
    
    def close(self):
        """Close the admin client connection"""
        if self.admin_client:
            self.admin_client.close()
            logger.info("Kafka admin client closed")

# Alternative method using subprocess (fallback)
def create_topic_with_cli(topic_name, bootstrap_server="localhost:9092", 
                         partitions=1, replication_factor=1):
    """
    Create Kafka topic using CLI command via subprocess
    This is a fallback method if kafka-python admin doesn't work
    """
    cmd = [
        "kafka-topics", "--create",
        "--topic", topic_name,
        "--bootstrap-server", bootstrap_server,
        "--partitions", str(partitions),
        "--replication-factor", str(replication_factor)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info(f"✅ Topic '{topic_name}' created successfully via CLI")
            return True
        else:
            if "already exists" in result.stderr:
                logger.warning(f"Topic '{topic_name}' already exists")
                return True
            else:
                logger.error(f"CLI command failed: {result.stderr}")
                return False
    except subprocess.TimeoutExpired:
        logger.error("CLI command timed out")
        return False
    except FileNotFoundError:
        logger.error("kafka-topics command not found in PATH")
        return False
    except Exception as e:
        logger.error(f"CLI command failed: {e}")
        return False

# Method using simple kafka client check + CLI
def create_topic_safe(topic_name, bootstrap_server="localhost:9092", 
                     partitions=1, replication_factor=1, max_retries=3):
    """
    Safe topic creation with fallback methods and retries
    """
    logger.info(f"Creating topic '{topic_name}' with {partitions} partitions...")
    
    # Method 1: Try kafka-python admin client
    try:
        manager = KafkaTopicManager(bootstrap_server)
        if manager.connect():
            success = manager.create_topic(
                topic_name, 
                num_partitions=partitions,
                replication_factor=replication_factor
            )
            manager.close()
            if success:
                return True
        logger.warning("kafka-python admin method failed, trying CLI fallback...")
    except Exception as e:
        logger.warning(f"kafka-python method failed: {e}")
    
    # Method 2: Fallback to CLI
    for attempt in range(max_retries):
        logger.info(f"CLI attempt {attempt + 1}/{max_retries}")
        if create_topic_with_cli(topic_name, bootstrap_server, partitions, replication_factor):
            return True
        if attempt < max_retries - 1:
            time.sleep(2)  # Wait before retry
    
    logger.error(f"All methods failed to create topic '{topic_name}'")
    return False

# Convenience functions for common use cases
def create_audio_transcription_topic(bootstrap_server="localhost:9092"):
    """Create the standard audio-transcription topic"""
    return create_topic_safe(
        topic_name="audio-transcription",
        bootstrap_server=bootstrap_server,
        partitions=1,
        replication_factor=1
    )

def setup_kafka_topics_for_project(bootstrap_server="localhost:9092"):
    """Setup all necessary Kafka topics for the audio transcription project"""
    topics_to_create = [
        {
            "name": "audio-transcription",
            "partitions": 1,
            "replication_factor": 1,
            "description": "Main topic for audio transcription jobs"
        },
        {
            "name": "transcription-results", 
            "partitions": 1,
            "replication_factor": 1,
            "description": "Optional topic for storing transcription results"
        },
        {
            "name": "transcription-errors",
            "partitions": 1, 
            "replication_factor": 1,
            "description": "Optional topic for failed transcription jobs"
        }
    ]
    
    success_count = 0
    for topic_config in topics_to_create:
        logger.info(f"Creating {topic_config['description']}")
        if create_topic_safe(
            topic_name=topic_config["name"],
            bootstrap_server=bootstrap_server,
            partitions=topic_config["partitions"],
            replication_factor=topic_config["replication_factor"]
        ):
            success_count += 1
        else:
            logger.error(f"Failed to create topic: {topic_config['name']}")
    
    logger.info(f"Successfully created {success_count}/{len(topics_to_create)} topics")
    return success_count == len(topics_to_create)

# Main function for command line usage
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Kafka Topic Creator for Audio Transcription")
    parser.add_argument("--topic", default="audio-transcription", help="Topic name to create")
    parser.add_argument("--server", default="localhost:9092", help="Kafka bootstrap server")
    parser.add_argument("--partitions", type=int, default=1, help="Number of partitions")
    parser.add_argument("--replication", type=int, default=1, help="Replication factor")
    parser.add_argument("--setup-all", action="store_true", help="Setup all project topics")
    parser.add_argument("--list", action="store_true", help="List existing topics")
    parser.add_argument("--delete", help="Delete specified topic")
    
    args = parser.parse_args()
    
    if args.list:
        # List topics
        manager = KafkaTopicManager(args.server)
        if manager.connect():
            topics = manager.list_topics()
            logger.info(f"Existing topics: {topics}")
            manager.close()
        return
    
    if args.delete:
        # Delete topic
        manager = KafkaTopicManager(args.server)
        if manager.connect():
            success = manager.delete_topic(args.delete)
            manager.close()
            sys.exit(0 if success else 1)
        return
    
    if args.setup_all:
        # Setup all project topics
        success = setup_kafka_topics_for_project(args.server)
        sys.exit(0 if success else 1)
    else:
        # Create single topic
        success = create_topic_safe(
            topic_name=args.topic,
            bootstrap_server=args.server,
            partitions=args.partitions,
            replication_factor=args.replication
        )
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()