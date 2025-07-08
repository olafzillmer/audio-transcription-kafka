#!/usr/bin/env python3
"""
Demo: Kafka Setup mit .env Integration
Zeigt alle verfügbaren Methoden zur Kafka-Topic-Erstellung
"""

import os
from dotenv import load_dotenv

# .env laden
load_dotenv()

def demo_all_methods():
    """Demonstriert alle verfügbaren Kafka-Setup-Methoden"""
    
    print("🎵 Kafka Topic Setup Demo")
    print("=" * 50)
    
    # Zeige aktuelle .env Konfiguration
    print("\n📋 Current .env Configuration:")
    print(f"   KAFKA_BOOTSTRAP_SERVERS: {os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'NOT SET')}")
    print(f"   KAFKA_TOPIC_AUDIO: {os.getenv('KAFKA_TOPIC_AUDIO', 'NOT SET')}")
    print(f"   KAFKA_CONSUMER_GROUP: {os.getenv('KAFKA_CONSUMER_GROUP', 'NOT SET')}")
    
    print("\n🔧 Available Setup Methods:")
    print("-" * 30)
    
    # Method 1: Config-Klasse (empfohlen für Integration)
    print("\n1️⃣ Via Config-Klasse (empfohlen für Services):")
    print("   from config import Config")
    print("   Config.ensure_kafka_topic()  # Nur Topic")
    print("   Config.setup_all()           # Topic + Upload-Folder")
    
    try:
        from config import Config
        print("   ✅ Config class available")
        
        # Test Connection (ohne Topic zu erstellen)
        kafka_servers = Config.KAFKA_BOOTSTRAP_SERVERS
        topic_name = Config.KAFKA_TOPIC_AUDIO
        print(f"   📡 Would use: {kafka_servers}")
        print(f"   📋 Would create topic: {topic_name}")
        
    except ImportError as e:
        print(f"   ❌ Config class not available: {e}")
    
    # Method 2: Simple Setup
    print("\n2️⃣ Via Simple Setup (empfohlen für Scripts):")
    print("   python simple_kafka_setup.py")
    print("   # oder in Python:")
    print("   from simple_kafka_setup import setup_audio_transcription_kafka")
    print("   setup_audio_transcription_kafka()")
    
    try:
        from simple_kafka_setup import get_kafka_config
        config = get_kafka_config()
        print("   ✅ Simple setup available")
        print(f"   📡 Would use: {config['bootstrap_servers']}")
        print(f"   📋 Would create topic: {config['topic_audio']}")
    except ImportError as e:
        print(f"   ❌ Simple setup not available: {e}")
    
    # Method 3: Advanced Topic Creator
    print("\n3️⃣ Via Advanced Topic Creator (empfohlen für Management):")
    print("   python kafka_topic_creator.py                    # Erstellt Standard-Topic")
    print("   python kafka_topic_creator.py --setup-all        # Erstellt alle Topics")
    print("   python kafka_topic_creator.py --list             # Listet Topics auf")
    print("   python kafka_topic_creator.py --show-config      # Zeigt Konfiguration")
    
    # Method 4: Direct CLI (fallback)
    print("\n4️⃣ Via Kafka CLI (fallback wenn Python-Methoden nicht funktionieren):")
    kafka_server = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    topic_name = os.getenv('KAFKA_TOPIC_AUDIO', 'audio-transcription')
    print(f"   kafka-topics --create \\")
    print(f"     --topic {topic_name} \\")
    print(f"     --bootstrap-server {kafka_server} \\")
    print(f"     --partitions 1 --replication-factor 1")
    
    print("\n✨ Recommendation:")
    print("   • For services: Use Config.setup_all() in your main()")
    print("   • For scripts: Use simple_kafka_setup.py")
    print("   • For management: Use kafka_topic_creator.py")
    print("   • For debugging: Use kafka_topic_creator.py --show-config")

def test_kafka_connection():
    """Testet die Kafka-Verbindung ohne Topics zu erstellen"""
    print("\n🔍 Testing Kafka Connection...")
    
    try:
        from kafka import KafkaAdminClient
        
        # Versuche Verbindung
        kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        client = KafkaAdminClient(
            bootstrap_servers=kafka_servers,
            client_id="demo_test",
            request_timeout_ms=5000
        )
        
        # Liste Topics auf (quick test)
        topics = client.list_topics()
        client.close()
        
        print(f"   ✅ Kafka connection successful!")
        print(f"   📡 Server: {kafka_servers}")
        print(f"   📋 Existing topics: {len(topics)}")
        if topics:
            audio_topic = os.getenv('KAFKA_TOPIC_AUDIO', 'audio-transcription')
            if audio_topic in topics:
                print(f"   ✅ Audio topic '{audio_topic}' already exists")
            else:
                print(f"   ⚠️ Audio topic '{audio_topic}' does not exist yet")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Kafka connection failed: {e}")
        print(f"   🔧 Check if Kafka is running at: {kafka_servers}")
        return False

if __name__ == "__main__":
    # Demo all methods
    demo_all_methods()
    
    # Test connection
    connection_ok = test_kafka_connection()
    
    print("\n" + "=" * 50)
    if connection_ok:
        print("🎉 Ready to create topics! Choose your preferred method above.")
    else:
        print("⚠️ Fix Kafka connection first, then run topic creation.")
    print("=" * 50)