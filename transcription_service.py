import os
import json
import asyncio
import threading
import multiprocessing
import logging
from datetime import datetime
import websockets
import torch
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

from config import Config
from transcription_logic import process_audio_file

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# IMPORTANT: For prefork workers to avoid CUDA errors (migrated from tasks.py)
try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass

class TranscriptionService:
    """Main service that consumes Kafka messages and provides WebSocket updates"""
    
    def __init__(self):
        self.pipe = None  # AI pipeline (lazy loaded)
        self.kafka_consumer = None
        self.websocket_clients = {}  # {request_id: set_of_websocket_connections}
        self.current_status = {
            "status": "idle",
            "current_task": None,
            "queue_length": 0,
            "uptime_start": datetime.now(),
            "processed_count": 0,
            "error_count": 0
        }
        self._running = False

    def get_pipeline(self):
        """
        Lazy loading of AI model (migrated from tasks.py get_pipeline())
        Loads the AI model and pipeline only once when first needed.
        """
        if self.pipe is None:
            logger.info("Pipeline not found. Initializing AI model for the first time...")
            device = Config.GPU_DEVICE
            model_id = Config.MODEL_ID
            torch_dtype = torch.float16 if "cuda" in device else torch.float32

            try:
                model = AutoModelForSpeechSeq2Seq.from_pretrained(
                    model_id,
                    torch_dtype=torch_dtype,
                    low_cpu_mem_usage=True,
                    use_safetensors=True,
                )
                model.to(device)
                processor = AutoProcessor.from_pretrained(model_id)
                
                self.pipe = pipeline(
                    "automatic-speech-recognition",
                    model=model,
                    tokenizer=processor.tokenizer,
                    feature_extractor=processor.feature_extractor,
                    max_new_tokens=128,
                    chunk_length_s=30,
                    batch_size=16,
                    return_timestamps=False,
                    torch_dtype=torch_dtype,
                    device=device,
                )
                logger.info(f"AI Model loaded successfully on device {device}")
            except Exception as e:
                logger.error(f"Failed to load AI model: {e}")
                raise
        
        return self.pipe

    async def broadcast_to_clients(self, request_id, message):
        """Send WebSocket message to all clients listening for this request_id"""
        if request_id in self.websocket_clients:
            disconnected_clients = []
            for websocket in self.websocket_clients[request_id].copy():
                try:
                    await websocket.send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    disconnected_clients.append(websocket)
                except Exception as e:
                    logger.warning(f"Error sending message to WebSocket client: {e}")
                    disconnected_clients.append(websocket)
            
            # Clean up disconnected clients
            for websocket in disconnected_clients:
                self.websocket_clients[request_id].discard(websocket)
                
            # Remove empty sets
            if not self.websocket_clients[request_id]:
                del self.websocket_clients[request_id]

    async def broadcast_status_update(self):
        """Broadcast current service status to all connected clients"""
        status_message = {
            "type": "status_update",
            "data": {
                **self.current_status,
                "uptime_minutes": round((datetime.now() - self.current_status["uptime_start"]).total_seconds() / 60, 1)
            }
        }
        
        # Send to all clients (regardless of request_id)
        all_clients = set()
        for client_set in self.websocket_clients.values():
            all_clients.update(client_set)
            
        disconnected_clients = []
        for websocket in all_clients:
            try:
                await websocket.send(json.dumps(status_message))
            except:
                disconnected_clients.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected_clients:
            for request_id, client_set in list(self.websocket_clients.items()):
                client_set.discard(websocket)
                if not client_set:
                    del self.websocket_clients[request_id]

    def process_transcription_task(self, message_data):
        """
        Process a single transcription task (migrated from tasks.py transcribe_task)
        This runs in the Kafka consumer thread
        """
        request_id = message_data.get("request_id")
        filepath = message_data.get("file_path")
        
        logger.info(f"Starting transcription for request {request_id}")
        
        # Update status
        self.current_status.update({
            "status": "processing",
            "current_task": {
                "request_id": request_id,
                "filename": os.path.basename(filepath),
                "started_at": datetime.now().isoformat()
            }
        })
        
        try:
            # Load AI pipeline (lazy loading)
            pipeline_instance = self.get_pipeline()
            
            # Process the audio file (migrated logic)
            result_data = process_audio_file(filepath, pipeline_instance)
            
            # Success message
            success_message = {
                "type": "transcription_complete",
                "request_id": request_id,
                "status": "SUCCESS", 
                "result": result_data,
                "completed_at": datetime.now().isoformat()
            }
            
            # Send via WebSocket (replaces external_socketio.emit)
            asyncio.run_coroutine_threadsafe(
                self.broadcast_to_clients(request_id, success_message),
                self.websocket_loop
            )
            
            self.current_status["processed_count"] += 1
            logger.info(f"Transcription completed for request {request_id}")
            
        except Exception as e:
            logger.error(f"Error during transcription of {request_id}: {e}")
            
            # Error message (migrated from tasks.py error handling)
            error_message = {
                "type": "transcription_error",
                "request_id": request_id,
                "status": "FAILURE",
                "error": str(e),
                "failed_at": datetime.now().isoformat()
            }
            
            # Send error via WebSocket
            asyncio.run_coroutine_threadsafe(
                self.broadcast_to_clients(request_id, error_message),
                self.websocket_loop
            )
            
            self.current_status["error_count"] += 1
            
        finally:
            # File cleanup (migrated from tasks.py)
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"Cleaned up file: {filepath}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup file {filepath}: {e}")
            
            # Reset status
            self.current_status.update({
                "status": "idle",
                "current_task": None
            })

    def start_kafka_consumer(self):
        """Start the Kafka consumer in a separate thread"""
        try:
            self.kafka_consumer = KafkaConsumer(
                Config.KAFKA_TOPIC_AUDIO,
                bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
                group_id=Config.KAFKA_CONSUMER_GROUP,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest',
                enable_auto_commit=False,  # Manual commit for reliability
                consumer_timeout_ms=1000   # Timeout to allow status updates
            )
            
            logger.info(f"Kafka Consumer connected to topic: {Config.KAFKA_TOPIC_AUDIO}")
            
            while self._running:
                try:
                    message_batch = self.kafka_consumer.poll(timeout_ms=1000)
                    
                    for topic_partition, messages in message_batch.items():
                        for message in messages:
                            if not self._running:
                                break
                                
                            logger.info(f"Received message: {message.value}")
                            
                            # Update queue length (approximate)
                            self.current_status["queue_length"] = len(messages)
                            
                            # Process the transcription task
                            self.process_transcription_task(message.value)
                            
                            # Manual commit after successful processing
                            self.kafka_consumer.commit_async()
                    
                    # Update queue length when no messages
                    if not message_batch:
                        self.current_status["queue_length"] = 0
                        
                except Exception as e:
                    logger.error(f"Error in Kafka consumer: {e}")
                    self.current_status["error_count"] += 1
                    
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise
        finally:
            if self.kafka_consumer:
                self.kafka_consumer.close()

    async def handle_websocket_client(self, websocket, path):
        """Handle individual WebSocket connections (migrated from app_websockets.py)"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"WebSocket client connected: {client_id}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get("type") == "join":
                        # Client wants to listen for updates on a specific request
                        request_id = data.get("request_id")
                        if request_id:
                            if request_id not in self.websocket_clients:
                                self.websocket_clients[request_id] = set()
                            self.websocket_clients[request_id].add(websocket)
                            logger.info(f"Client {client_id} joined room: {request_id}")
                            
                            # Send immediate status update
                            await websocket.send(json.dumps({
                                "type": "joined",
                                "request_id": request_id,
                                "current_status": self.current_status
                            }))
                    
                    elif data.get("type") == "get_status":
                        # Client requests current service status
                        await self.broadcast_status_update()
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client {client_id}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error handling WebSocket client {client_id}: {e}")
        finally:
            # Clean up client from all rooms
            for request_id, client_set in list(self.websocket_clients.items()):
                client_set.discard(websocket)
                if not client_set:
                    del self.websocket_clients[request_id]

    async def start_websocket_server(self):
        """Start the WebSocket server"""
        logger.info(f"Starting WebSocket server on {Config.WEBSOCKET_HOST}:{Config.WEBSOCKET_PORT}")
        
        # Store the event loop for cross-thread communication
        self.websocket_loop = asyncio.get_event_loop()
        
        # Start periodic status broadcasts
        asyncio.create_task(self.periodic_status_broadcast())
        
        async with websockets.serve(
            self.handle_websocket_client, 
            Config.WEBSOCKET_HOST, 
            Config.WEBSOCKET_PORT
        ):
            await asyncio.Future()  # Run forever

    async def periodic_status_broadcast(self):
        """Periodically broadcast status updates to all clients"""
        while self._running:
            await asyncio.sleep(30)  # Every 30 seconds
            await self.broadcast_status_update()

    def start(self):
        """Start the complete service"""
        logger.info("Starting Transcription Service...")
        self._running = True
        
        # Start Kafka consumer in background thread
        kafka_thread = threading.Thread(target=self.start_kafka_consumer, daemon=True)
        kafka_thread.start()
        
        # Start WebSocket server (blocks)
        try:
            asyncio.run(self.start_websocket_server())
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        finally:
            self.stop()

    def stop(self):
        """Graceful shutdown"""
        logger.info("Stopping Transcription Service...")
        self._running = False
        
        if self.kafka_consumer:
            self.kafka_consumer.close()

def main():
    """Entry point for the Transcription Service"""
    service = TranscriptionService()
    service.start()

if __name__ == '__main__':
    main()