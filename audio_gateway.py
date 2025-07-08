import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from kafka import KafkaProducer
from kafka.errors import KafkaError
import logging
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_app(testing=False):
    app = Flask(__name__)
    app.config.update({
        'TESTING': testing,
        'API_KEY': Config.API_KEY,
        'UPLOAD_FOLDER': Config.UPLOAD_FOLDER,
        'MAX_CONTENT_LENGTH': Config.MAX_CONTENT_LENGTH
    })
    
    # Ensure upload folder exists
    Config.ensure_upload_folder()
    
    # Initialize Kafka Producer
    if not testing:
        try:
            producer = KafkaProducer(
                bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',  # Wait for all replicas to acknowledge
                retries=3,
                retry_backoff_ms=1000
            )
            app.kafka_producer = producer
            logger.info(f"Kafka Producer connected to {Config.KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
    else:
        app.kafka_producer = None  # Will be mocked in tests

    def allowed_file(filename):
        """Check if uploaded file has allowed extension"""
        ALLOWED_EXTENSIONS = {'mp3', 'm4a', 'wav', 'flac'}
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    @app.route('/upload', methods=['POST'])
    def upload_audio():
        """Handle MP3/audio file upload and send to Kafka queue"""
        # API Key validation (migrated from original app.py)
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != app.config['API_KEY']:
            logger.warning(f"Unauthorized access attempt with key: {api_key}")
            return jsonify({"error": "Unauthorized"}), 401
        
        # File validation (migrated and enhanced)
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type. Allowed: mp3, m4a, wav, flac"}), 400

        try:
            # Save file securely (migrated from original)
            filename = secure_filename(file.filename)
            # Add timestamp to prevent filename collisions
            timestamp_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], timestamp_filename)
            file.save(filepath)
            
            # Generate unique request ID
            request_id = str(uuid.uuid4())
            
            # Create Kafka message (replaces Celery task)
            message = {
                "file_path": filepath,
                "original_filename": filename,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "file_size_bytes": os.path.getsize(filepath)
            }
            
            # Send to Kafka (replaces celery_app.send_task)
            if app.kafka_producer:
                future = app.kafka_producer.send(Config.KAFKA_TOPIC_AUDIO, value=message)
                # Wait for send to complete (with timeout)
                record_metadata = future.get(timeout=10)
                logger.info(f"Message sent to Kafka topic {record_metadata.topic}, partition {record_metadata.partition}, offset {record_metadata.offset}")
            
            logger.info(f"Audio file queued for transcription: {request_id}")
            return jsonify({
                "message": "Audio file queued for transcription",
                "request_id": request_id,
                "original_filename": filename
            }), 202
            
        except KafkaError as e:
            logger.error(f"Kafka error: {e}")
            # Clean up file if Kafka send failed
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"error": "Service temporarily unavailable. Please try again later."}), 503
            
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            # Clean up file if processing failed
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"error": "Internal server error"}), 500

    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint (migrated from original)"""
        health_status = {"status": "Audio-Gateway is healthy"}
        
        # Add Kafka connectivity check
        if app.kafka_producer:
            try:
                # Quick check if Kafka is responsive
                metadata = app.kafka_producer.partitions_for(Config.KAFKA_TOPIC_AUDIO)
                if metadata is not None:
                    health_status["kafka"] = "connected"
                else:
                    health_status["kafka"] = "topic_not_found"
            except Exception:
                health_status["kafka"] = "disconnected"
        else:
            health_status["kafka"] = "testing_mode"
            
        return jsonify(health_status), 200

    @app.route('/status/<request_id>', methods=['GET'])
    def get_status(request_id):
        """Get processing status for a request ID"""
        # This is a placeholder - in a full implementation, you might query
        # a status store or the Transcription-Service directly
        return jsonify({
            "request_id": request_id,
            "message": "Connect to WebSocket for real-time updates",
            "websocket_url": f"ws://{Config.WEBSOCKET_HOST}:{Config.WEBSOCKET_PORT}"
        }), 200

    @app.teardown_appcontext
    def close_kafka_producer(error):
        """Cleanup Kafka producer on app teardown"""
        if hasattr(app, 'kafka_producer') and app.kafka_producer:
            app.kafka_producer.close()

    return app

def main():
    """Entry point for running the Audio-Gateway"""
    app = create_app(testing=False)
    logger.info(f"Starting Audio-Gateway on {Config.GATEWAY_HOST}:{Config.GATEWAY_PORT}")
    logger.info(f"Kafka Topic: {Config.KAFKA_TOPIC_AUDIO}")
    logger.info(f"Upload Folder: {Config.UPLOAD_FOLDER}")
    
    app.run(
        host=Config.GATEWAY_HOST,
        port=Config.GATEWAY_PORT,
        debug=False,
        threaded=True
    )

if __name__ == '__main__':
    main()