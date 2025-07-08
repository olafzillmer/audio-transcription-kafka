#!/usr/bin/env python3
"""
WebSocket Test Client für Audio Transcription Service
Verwendung:
  python websocket_test.py                    # Service Status abrufen
  python websocket_test.py REQUEST_ID         # Auf spezifische Transkription warten
  python websocket_test.py --monitor          # Dauerhaft alle Updates anzeigen
"""

import asyncio
import json
import sys
import time
import argparse
import websockets
from datetime import datetime

class WebSocketTestClient:
    def __init__(self, websocket_url="ws://localhost:8765"):
        self.websocket_url = websocket_url
        self.connected = False

    async def get_service_status(self):
        """Ruft einmalig den Service-Status ab"""
        try:
            async with websockets.connect(self.websocket_url, timeout=5) as websocket:
                print(f"✅ Connected to {self.websocket_url}")
                
                # Status anfordern
                status_request = {"type": "get_status"}
                await websocket.send(json.dumps(status_request))
                print("📤 Sent status request...")
                
                # Auf Antwort warten
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10)
                    data = json.loads(response)
                    
                    print("\n📊 Service Status:")
                    print("=" * 50)
                    if data.get("type") == "status_update":
                        status = data["data"]
                        print(f"Status: {status.get('status', 'unknown')}")
                        print(f"Uptime: {status.get('uptime_minutes', 0):.1f} minutes")
                        print(f"Processed: {status.get('processed_count', 0)} files")
                        print(f"Errors: {status.get('error_count', 0)}")
                        print(f"Queue Length: {status.get('queue_length', 0)}")
                        
                        current_task = status.get('current_task')
                        if current_task:
                            print(f"Current Task: {current_task.get('filename')} (ID: {current_task.get('request_id')})")
                        else:
                            print("Current Task: None (idle)")
                    else:
                        print(f"Unknown response: {data}")
                        
                except asyncio.TimeoutError:
                    print("⏰ Timeout waiting for status response")
                    
        except websockets.exceptions.ConnectionError:
            print(f"❌ Could not connect to WebSocket server at {self.websocket_url}")
            print("   Make sure the Transcription Service is running.")
        except Exception as e:
            print(f"❌ Error: {e}")

    async def monitor_request(self, request_id):
        """Wartet auf Updates für eine spezifische Request ID"""
        try:
            async with websockets.connect(self.websocket_url, timeout=5) as websocket:
                print(f"✅ Connected to {self.websocket_url}")
                
                # Room beitreten
                join_request = {
                    "type": "join",
                    "request_id": request_id
                }
                await websocket.send(json.dumps(join_request))
                print(f"📤 Joined room for request: {request_id}")
                print("⏳ Waiting for transcription updates...\n")
                
                # Auf Updates warten
                async for message in websocket:
                    data = json.loads(message)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    if data.get("type") == "joined":
                        print(f"[{timestamp}] ✅ Successfully joined room")
                        current_status = data.get("current_status", {})
                        print(f"[{timestamp}] Service status: {current_status.get('status', 'unknown')}")
                        
                    elif data.get("type") == "transcription_complete":
                        print(f"[{timestamp}] 🎉 Transcription completed!")
                        result = data.get("result", {})
                        print(f"[{timestamp}] Duration: {result.get('audio_duration_minutes', 0):.2f} minutes")
                        print(f"[{timestamp}] Words: {result.get('transcription_word_count', 0)}")
                        print(f"[{timestamp}] Text preview: {result.get('transcription', '')[:100]}...")
                        break
                        
                    elif data.get("type") == "transcription_error":
                        print(f"[{timestamp}] ❌ Transcription failed!")
                        print(f"[{timestamp}] Error: {data.get('error', 'Unknown error')}")
                        break
                        
                    elif data.get("type") == "status_update":
                        status = data.get("data", {})
                        print(f"[{timestamp}] 📊 Status: {status.get('status')} "
                              f"(Queue: {status.get('queue_length', 0)})")
                        
                    else:
                        print(f"[{timestamp}] 📨 Update: {data.get('type', 'unknown')}")
                        
        except websockets.exceptions.ConnectionError:
            print(f"❌ Could not connect to WebSocket server at {self.websocket_url}")
        except KeyboardInterrupt:
            print("\n👋 Disconnected by user")
        except Exception as e:
            print(f"❌ Error: {e}")

    async def monitor_all(self):
        """Dauerhaftes Monitoring aller Service-Updates"""
        try:
            async with websockets.connect(self.websocket_url, timeout=5) as websocket:
                print(f"✅ Connected to {self.websocket_url}")
                print("🔍 Monitoring all service updates... (Press Ctrl+C to stop)\n")
                
                # Regelmäßig Status abfragen
                async def periodic_status():
                    while True:
                        await asyncio.sleep(30)  # Alle 30 Sekunden
                        try:
                            status_request = {"type": "get_status"}
                            await websocket.send(json.dumps(status_request))
                        except:
                            break
                
                # Status-Task starten
                status_task = asyncio.create_task(periodic_status())
                
                # Auf alle Messages hören
                async for message in websocket:
                    data = json.loads(message)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    if data.get("type") == "status_update":
                        status = data.get("data", {})
                        print(f"[{timestamp}] 📊 {status.get('status', 'unknown')} - "
                              f"Queue: {status.get('queue_length', 0)}, "
                              f"Processed: {status.get('processed_count', 0)}, "
                              f"Errors: {status.get('error_count', 0)}")
                        
                    else:
                        print(f"[{timestamp}] 📨 {data.get('type', 'unknown')}: {data}")
                
                status_task.cancel()
                
        except websockets.exceptions.ConnectionError:
            print(f"❌ Could not connect to WebSocket server at {self.websocket_url}")
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped by user")
        except Exception as e:
            print(f"❌ Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="WebSocket Test Client for Audio Transcription Service")
    parser.add_argument("request_id", nargs="?", help="Request ID to monitor (from upload response)")
    parser.add_argument("--monitor", action="store_true", help="Monitor all service updates continuously")
    parser.add_argument("--url", default="ws://localhost:8765", help="WebSocket URL (default: ws://localhost:8765)")
    
    args = parser.parse_args()
    
    client = WebSocketTestClient(args.url)
    
    if args.monitor:
        print("🔍 Starting continuous monitoring mode...")
        asyncio.run(client.monitor_all())
    elif args.request_id:
        print(f"⏳ Monitoring request: {args.request_id}")
        asyncio.run(client.monitor_request(args.request_id))
    else:
        print("📊 Getting service status...")
        asyncio.run(client.get_service_status())

if __name__ == "__main__":
    main()