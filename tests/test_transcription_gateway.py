import pytest
import asyncio
import json
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from transcription_service import TranscriptionService
from transcription_logic import count_words_in_german_text, process_audio_file

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit

class TestTranscriptionLogic:
    """Test the core transcription logic (migrated from test_transcription_logic.py)"""
    
    def test_count_words_simple(self):
        """Test word counting with simple German text (migrated)"""
        text = "Hallo Welt, dies ist ein Test."
        assert count_words_in_german_text(text) == 6

    def test_count_words_with_numbers_and_punctuation(self):
        """Test word counting with numbers and punctuation (migrated)"""
        text = "Der Preis beträgt 5,99€! Wow."
        assert count_words_in_german_text(text) == 4

    def test_count_words_empty_string(self):
        """Test word counting with empty string (migrated)"""
        text = ""
        assert count_words_in_german_text(text) == 0

    @patch('transcription_logic.get_audio_length_in_minutes')
    def test_process_audio_file_structure(self, mock_audio_length):
        """Test that process_audio_file returns correct structure (NEW)"""
        # Mock dependencies
        mock_audio_length.return_value = 2.5
        
        mock_pipeline = Mock()
        mock_pipeline.return_value = {"text": "Dies ist ein Test mit acht Wörtern hier."}
        
        result = process_audio_file("/fake/path.mp3", mock_pipeline)
        
        # Check structure
        assert "audio_duration_minutes" in result
        assert "transcription_word_count" in result
        assert "estimated_reading_time_minutes" in result
        assert "transcription" in result
        assert "prompts" in result
        
        # Check prompts structure
        prompts = result["prompts"]
        assert "summary_tasks_and_todos" in prompts
        assert "presentation_structure" in prompts
        assert "journalistic_summary" in prompts

class TestTranscriptionServiceCore:
    """Test TranscriptionService class functionality"""
    
    def test_service_initialization(self):
        """Test service initializes with correct default state"""
        service = TranscriptionService()
        
        assert service.pipe is None
        assert service.websocket_clients == {}
        assert service.current_status["status"] == "idle"
        assert service.current_status["processed_count"] == 0
        assert service.current_status["error_count"] == 0

    @patch('transcription_service.AutoModelForSpeechSeq2Seq')
    @patch('transcription_service.AutoProcessor')  
    @patch('transcription_service.pipeline')
    def test_get_pipeline_lazy_loading(self, mock_pipeline, mock_processor, mock_model):
        """Test that AI pipeline is loaded only once (migrated from tasks.py pattern)"""
        service = TranscriptionService()
        
        # Mock the AI components
        mock_pipeline.return_value = "fake_pipeline"
        
        # First call should load the pipeline
        pipeline1 = service.get_pipeline()
        assert pipeline1 == "fake_pipeline"
        
        # Second call should return the same instance without reloading
        pipeline2 = service.get_pipeline()
        assert pipeline2 == pipeline1
        
        # Verify that the model was only loaded once
        mock_model.from_pretrained.assert_called_once()
        mock_processor.from_pretrained.assert_called_once()
        mock_pipeline.assert_called_once()

class TestWebSocketFunctionality:
    """Test WebSocket handling (migrated and adapted from test_websockets.py)"""
    
    @pytest.fixture
    def service(self):
        """Create a TranscriptionService for testing"""
        return TranscriptionService()

    def test_websocket_client_joining(self, service):
        """Test client can join a specific request room (migrated concept)"""
        # Simulate a WebSocket connection
        mock_websocket = Mock()
        request_id = "test-request-123"
        
        # Manually add client to room (simulates the join process)
        if request_id not in service.websocket_clients:
            service.websocket_clients[request_id] = set()
        service.websocket_clients[request_id].add(mock_websocket)
        
        # Verify client is in the room
        assert mock_websocket in service.websocket_clients[request_id]
        assert len(service.websocket_clients[request_id]) == 1

    @pytest.mark.asyncio
    async def test_broadcast_to_specific_clients(self, service):
        """Test broadcasting messages to specific request clients (migrated pattern)"""
        # Setup mock clients for different requests
        client1_ws = Mock()
        client2_ws = Mock()
        
        # Add clients to different rooms
        service.websocket_clients = {
            "request-1": {client1_ws},
            "request-2": {client2_ws}
        }
        
        # Mock successful send operations
        client1_ws.send = AsyncMock()
        client2_ws.send = AsyncMock()
        
        test_message = {"status": "SUCCESS", "result": "Test transcript"}
        
        # Broadcast to request-1 only
        await service.broadcast_to_clients("request-1", test_message)
        
        # Verify only client1 received the message
        client1_ws.send.assert_called_once()
        client2_ws.send.assert_not_called()
        
        # Verify message content
        sent_message = json.loads(client1_ws.send.call_args[0][0])
        assert sent_message == test_message

    @pytest.mark.asyncio
    async def test_broadcast_handles_disconnected_clients(self, service):
        """Test that disconnected clients are cleaned up (NEW - robustness)"""
        # Setup clients
        connected_client = Mock()
        disconnected_client = Mock()
        
        # Mock WebSocket responses
        connected_client.send = AsyncMock()
        disconnected_client.send = AsyncMock()
        disconnected_client.send.side_effect = Exception("Connection closed")
        
        request_id = "test-request"
        service.websocket_clients[request_id] = {connected_client, disconnected_client}
        
        test_message = {"status": "SUCCESS"}
        await service.broadcast_to_clients(request_id, test_message)
        
        # Verify disconnected client was removed
        assert disconnected_client not in service.websocket_clients[request_id]
        assert connected_client in service.websocket_clients[request_id]

class TestKafkaConsumerIntegration:
    """Test Kafka consumer functionality (NEW - Kafka-specific tests)"""
    
    @pytest.fixture
    def service(self):
        return TranscriptionService()

    @patch('transcription_service.process_audio_file')
    @patch.object(TranscriptionService, 'get_pipeline')
    def test_process_transcription_task_success(self, mock_get_pipeline, mock_process_audio, service):
        """Test successful transcription processing (migrated from tasks.py pattern)"""
        # Setup mocks
        mock_pipeline = Mock()
        mock_get_pipeline.return_value = mock_pipeline
        mock_process_audio.return_value = {
            "transcription": "Test transcript",
            "audio_duration_minutes": 2.5
        }
        
        # Create a message
        message_data = {
            "request_id": "test-123",
            "file_path": "/tmp/test.mp3"
        }
        
        # Mock the WebSocket broadcasting
        with patch.object(service, 'broadcast_to_clients') as mock_broadcast:
            with patch('asyncio.run_coroutine_threadsafe'):
                service.process_transcription_task(message_data)
        
        # Verify processing was called correctly
        mock_process_audio.assert_called_once_with("/tmp/test.mp3", mock_pipeline)
        
        # Verify status was updated
        assert service.current_status["processed_count"] == 1
        assert service.current_status["status"] == "idle"

    @patch('transcription_service.process_audio_file')
    @patch.object(TranscriptionService, 'get_pipeline')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_process_transcription_task_error_handling(self, mock_remove, mock_exists, 
                                                      mock_get_pipeline, mock_process_audio, service):
        """Test error handling in transcription processing (migrated from tasks.py)"""
        # Setup mocks
        mock_get_pipeline.return_value = Mock()
        mock_process_audio.side_effect = Exception("Processing failed")
        mock_exists.return_value = True
        
        message_data = {
            "request_id": "test-error",
            "file_path": "/tmp/error.mp3"
        }
        
        # Mock WebSocket broadcasting
        with patch.object(service, 'broadcast_to_clients') as mock_broadcast:
            with patch('asyncio.run_coroutine_threadsafe'):
                service.process_transcription_task(message_data)
        
        # Verify error was handled
        assert service.current_status["error_count"] == 1
        
        # Verify file cleanup was attempted
        mock_remove.assert_called_once_with("/tmp/error.mp3")

    @patch('transcription_service.KafkaConsumer')
    def test_kafka_consumer_initialization(self, mock_kafka_consumer, service):
        """Test Kafka consumer setup (NEW)"""
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        
        # Mock the polling to return no messages (to avoid infinite loop)
        mock_consumer_instance.poll.return_value = {}
        
        # Start consumer briefly
        service._running = True
        
        # Use a thread to start and quickly stop the consumer
        def start_and_stop():
            time.sleep(0.1)  # Let it start
            service._running = False
        
        stop_thread = threading.Thread(target=start_and_stop)
        stop_thread.start()
        
        # This should not block for long due to the stop mechanism
        service.start_kafka_consumer()
        
        stop_thread.join()
        
        # Verify consumer was created with correct parameters
        mock_kafka_consumer.assert_called_once()
        call_kwargs = mock_kafka_consumer.call_args[1]
        assert call_kwargs['group_id'] == 'transcription-workers'
        assert call_kwargs['enable_auto_commit'] is False

# Async test helper
class AsyncMock(Mock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)