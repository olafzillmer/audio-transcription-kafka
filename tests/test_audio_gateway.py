import io
import pytest
from unittest.mock import patch, Mock
from kafka.errors import KafkaTimeoutError

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit

def test_health_check(client):
    """Test the /health endpoint (migrated from original)"""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "Audio-Gateway is healthy"
    assert "kafka" in data

def test_health_check_with_kafka_status(client):
    """Test health check includes Kafka connectivity status"""
    # Mock Kafka producer to simulate connected state
    client.application.kafka_producer.partitions_for.return_value = {0, 1}
    
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data["kafka"] == "connected"

def test_upload_missing_api_key(client):
    """Test that request without API key is rejected (migrated)"""
    response = client.post('/upload')
    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"

def test_upload_wrong_api_key(client):
    """Test that request with wrong API key is rejected (migrated)"""
    headers = {'X-API-Key': 'wrong-key'}
    response = client.post('/upload', headers=headers)
    assert response.status_code == 401

def test_upload_no_file(client):
    """Test that request without file is rejected (migrated)"""
    headers = {'X-API-Key': 'test-key'}
    response = client.post('/upload', headers=headers)
    assert response.status_code == 400
    assert response.get_json()['error'] == 'No file part'

def test_upload_empty_filename(client):
    """Test that request with empty filename is rejected"""
    headers = {'X-API-Key': 'test-key'}
    data = {'file': (io.BytesIO(b"dummy audio data"), '')}
    response = client.post('/upload', headers=headers, data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.get_json()['error'] == 'No selected file'

def test_upload_invalid_file_type(client):
    """Test that invalid file types are rejected (NEW - enhanced validation)"""
    headers = {'X-API-Key': 'test-key'}
    data = {'file': (io.BytesIO(b"dummy data"), 'test.txt')}
    response = client.post('/upload', headers=headers, data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert "Invalid file type" in response.get_json()['error']

def test_upload_success_mp3(client, mock_kafka_producer):
    """Test successful MP3 upload and Kafka message sending (migrated and enhanced)"""
    headers = {'X-API-Key': 'test-key'}
    data = {'file': (io.BytesIO(b"dummy mp3 data"), 'test.mp3')}

    response = client.post('/upload', headers=headers, data=data, content_type='multipart/form-data')

    # Check HTTP response
    assert response.status_code == 202
    response_data = response.get_json()
    assert "request_id" in response_data
    assert response_data["original_filename"] == "test.mp3"
    assert "Audio file queued" in response_data["message"]

    # Check that Kafka producer was called (replaces Celery task check)
    mock_kafka_producer.send.assert_called_once()
    
    # Verify Kafka message content
    call_args = mock_kafka_producer.send.call_args
    topic = call_args[0][0]
    message = call_args[1]['value']
    
    assert topic == "audio-transcription"  # Default topic from config
    assert message["original_filename"] == "test.mp3"
    assert message["request_id"] == response_data["request_id"]
    assert "file_path" in message
    assert "timestamp" in message

def test_upload_success_m4a(client, mock_kafka_producer):
    """Test successful M4A upload (NEW - test enhanced file support)"""
    headers = {'X-API-Key': 'test-key'}
    data = {'file': (io.BytesIO(b"dummy m4a data"), 'test.m4a')}

    response = client.post('/upload', headers=headers, data=data, content_type='multipart/form-data')
    assert response.status_code == 202
    mock_kafka_producer.send.assert_called_once()

def test_upload_kafka_error_handling(client):
    """Test handling of Kafka errors (NEW - Kafka-specific error handling)"""
    headers = {'X-API-Key': 'test-key'}
    data = {'file': (io.BytesIO(b"dummy audio data"), 'test.mp3')}
    
    # Mock Kafka timeout error
    client.application.kafka_producer.send.side_effect = KafkaTimeoutError("Kafka unavailable")
    
    response = client.post('/upload', headers=headers, data=data, content_type='multipart/form-data')
    
    assert response.status_code == 503
    assert "Service temporarily unavailable" in response.get_json()["error"]

def test_upload_file_cleanup_on_kafka_error(client, temp_upload_dir):
    """Test that uploaded file is cleaned up when Kafka fails (NEW - reliability)"""
    headers = {'X-API-Key': 'test-key'}
    data = {'file': (io.BytesIO(b"dummy audio data"), 'test.mp3')}
    
    # Mock Kafka error
    client.application.kafka_producer.send.side_effect = Exception("Kafka error")
    
    # Count files before and after
    import os
    files_before = len(os.listdir(temp_upload_dir))
    
    response = client.post('/upload', headers=headers, data=data, content_type='multipart/form-data')
    
    files_after = len(os.listdir(temp_upload_dir))
    
    # File should be cleaned up on error
    assert files_after == files_before
    assert response.status_code == 500

def test_status_endpoint(client):
    """Test the status endpoint for request tracking (NEW)"""
    test_request_id = "test-request-123"
    response = client.get(f'/status/{test_request_id}')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["request_id"] == test_request_id
    assert "websocket_url" in data

def test_upload_creates_timestamped_filename(client, mock_kafka_producer, temp_upload_dir):
    """Test that uploaded files get timestamped filenames to prevent collisions (NEW)"""
    headers = {'X-API-Key': 'test-key'}
    data = {'file': (io.BytesIO(b"dummy audio data"), 'test.mp3')}

    response = client.post('/upload', headers=headers, data=data, content_type='multipart/form-data')
    assert response.status_code == 202
    
    # Check that the file was saved with timestamp prefix
    call_args = mock_kafka_producer.send.call_args
    message = call_args[1]['value']
    saved_filepath = message["file_path"]
    
    import os
    filename = os.path.basename(saved_filepath)
    # Should be like: 20250707_120000_test.mp3
    assert filename.endswith("_test.mp3")
    assert len(filename) > len("test.mp3")  # Has timestamp prefix