import pytest
import asyncio
import threading
import requests
import websockets
import json
import time
from pathlib import Path

# Mark all tests in this file as 'e2e'
pytestmark = pytest.mark.e2e

# Configuration for the test
TEST_AUDIO_FILE = Path(__file__).parent / "test_data" / "Tagesschau.mp3"
AUDIO_GATEWAY_URL = "http://127.0.0.1:5000"  # Audio-Gateway server
WEBSOCKET_URL = "ws://127.0.0.1:8765"        # Transcription-Service WebSocket
API_KEY = "test-key"  # Must match the API key in environment

@pytest.fixture(scope="module")
def audio_file():
    """Ensure test audio file exists (migrated)"""
    if not TEST_AUDIO_FILE.is_file():
        pytest.fail(f"Test audio file not found at: {TEST_AUDIO_FILE}")
    return TEST_AUDIO_FILE

def test_full_kafka_transcription_process(audio_file):
    """
    Test complete transcription process against LIVE Kafka-based services.
    
    Prerequisites: 
    - Kafka server running
    - Audio-Gateway running on port 5000 
    - Transcription-Service running on port 8765
    """
    result_received_event = threading.Event()
    transcription_result = {}
    connection_successful = threading.Event()

    async def websocket_client():
        """WebSocket client to receive transcription updates"""
        nonlocal transcription_result
        
        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                connection_successful.set()
                
                # Join room for our request (will be set after upload)
                join_message = {
                    "type": "join",
                    "request_id": task_id  # Will be available from outer scope
                }
                await websocket.send(json.dumps(join_message))
                
                # Listen for transcription updates
                async for message in websocket:
                    data = json.loads(message)
                    
                    if data.get("type") == "transcription_complete":
                        transcription_result = data
                        result_received_event.set()
                        break
                    elif data.get("type") == "transcription_error":
                        transcription_result = data
                        result_received_event.set()
                        break
                    elif data.get("type") == "joined":
                        print(f"E2E Test: Successfully joined room {data.get('request_id')}")
                        
        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")

    # Step 1: Upload audio file to Audio-Gateway
    try:
        with open(audio_file, "rb") as f:
            response = requests.post(
                f"{AUDIO_GATEWAY_URL}/upload",
                headers={"X-API-Key": API_KEY},
                files={"file": (audio_file.name, f, "audio/mpeg")},
                timeout=30
            )
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Could not connect to Audio-Gateway at {AUDIO_GATEWAY_URL}. Is it running?")
    
    # Verify upload was successful
    assert response.status_code == 202, f"Upload failed: {response.text}"
    upload_data = response.json()
    task_id = upload_data["request_id"]
    assert task_id is not None
    print(f"E2E Test: Audio uploaded, request_id: {task_id}")

    # Step 2: Connect to WebSocket and listen for updates
    websocket_thread = threading.Thread(target=lambda: asyncio.run(websocket_client()))
    websocket_thread.daemon = True
    websocket_thread.start()
    
    # Wait for WebSocket connection to be established
    if not connection_successful.wait(timeout=10):
        pytest.fail("Could not establish WebSocket connection within 10 seconds")
    
    # Step 3: Wait for transcription to complete
    print("E2E Test: Waiting for transcription to complete...")
    finished_in_time = result_received_event.wait(timeout=300)  # 5 minutes timeout
    
    # Step 4: Verify results
    if not finished_in_time:
        pytest.fail("E2E Test timed out: Transcription result not received within 5 minutes.")

    print(f"E2E Test: Received result: {transcription_result.get('type')}")
    
    # Check for errors
    if transcription_result.get("type") == "transcription_error":
        pytest.fail(f"Transcription failed: {transcription_result.get('error')}")
    
    # Verify successful transcription
    assert transcription_result.get("type") == "transcription_complete"
    assert transcription_result.get("status") == "SUCCESS"
    
    # Verify result structure
    result_data = transcription_result.get("result", {})
    assert "transcription" in result_data
    assert "audio_duration_minutes" in result_data
    assert "transcription_word_count" in result_data
    assert "prompts" in result_data
    
    # Content verification (adapted from original test)
    transcribed_text = result_data.get("transcription", "")
    print(f"\nE2E Test - Transcribed Text: {transcribed_text[:200]}...")  # First 200 chars
    
    # Basic content checks (adjust based on your test audio)
    assert len(transcribed_text) > 0, "Transcription should not be empty"
    
    # Test audio-specific checks (uncomment and adjust for your test file)
    # expected_keywords = ["Guten Abend", "Tagesschau", "Wetter"]
    # text_lower = transcribed_text.lower()
    # for keyword in expected_keywords:
    #     assert keyword.lower() in text_lower, f"Expected keyword '{keyword}' not found"

def test_audio_gateway_health_check():
    """Test that Audio-Gateway is healthy and reachable"""
    try:
        response = requests.get(f"{AUDIO_GATEWAY_URL}/health", timeout=5)
        assert response.status_code == 200
        health_data = response.json()
        assert health_data["status"] == "Audio-Gateway is healthy"
        print(f"Audio-Gateway health: {health_data}")
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Audio-Gateway at {AUDIO_GATEWAY_URL} is not reachable")

def test_transcription_service_websocket_connectivity():
    """Test that Transcription-Service WebSocket is accessible"""
    async def test_connection():
        try:
            async with websockets.connect(WEBSOCKET_URL, timeout=5) as websocket:
                # Send status request
                status_request = {"type": "get_status"}
                await websocket.send(json.dumps(status_request))
                
                # Should receive some response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                print(f"Transcription-Service status: {data.get('type', 'unknown')}")
                
        except Exception as e:
            pytest.fail(f"Could not connect to Transcription-Service WebSocket: {e}")
    
    asyncio.run(test_connection())

def test_kafka_integration_upload_without_processing():
    """Test that uploads reach Kafka queue even without full processing"""
    # Create a small dummy file for quick testing
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
        tmp_file.write(b"dummy audio data for kafka test")
        tmp_file.flush()
        
        try:
            # Upload the dummy file
            with open(tmp_file.name, "rb") as f:
                response = requests.post(
                    f"{AUDIO_GATEWAY_URL}/upload",
                    headers={"X-API-Key": API_KEY},
                    files={"file": ("test_kafka.mp3", f, "audio/mpeg")},
                    timeout=10
                )
            
            assert response.status_code == 202
            request_id = response.json()["request_id"]
            print(f"Kafka integration test: uploaded with request_id {request_id}")
            
        finally:
            # Cleanup
            os.unlink(tmp_file.name)

# Performance test
def test_multiple_concurrent_uploads():
    """Test system handles multiple uploads (stress test)"""
    import tempfile
    import os
    import concurrent.futures
    
    def upload_dummy_file(file_number):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_file.write(b"dummy audio data " * 100)  # Slightly larger file
            tmp_file.flush()
            
            try:
                with open(tmp_file.name, "rb") as f:
                    response = requests.post(
                        f"{AUDIO_GATEWAY_URL}/upload",
                        headers={"X-API-Key": API_KEY},
                        files={"file": (f"test_{file_number}.mp3", f, "audio/mpeg")},
                        timeout=30
                    )
                return response.status_code == 202
            finally:
                os.unlink(tmp_file.name)
    
    # Upload 3 files concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(upload_dummy_file, i) for i in range(3)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    # All uploads should succeed
    assert all(results), "Not all concurrent uploads succeeded"
    print("Concurrent upload test: All uploads successful")