# Audio Transcription Service mit Kafka

Ein robustes, Kafka-basiertes System für Audio-Transkription mit AI-Models (Whisper). Das System besteht aus zwei entkoppelten Services: einem **Audio-Gateway** für File-Upload und einem **Transcription-Service** für die AI-Verarbeitung.

## 🏗️ Architektur

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐
│   Audio-Gateway │    │      Kafka      │    │ Transcription-      │
│   (Flask)       │───▶│    Message      │───▶│ Service             │
│                 │    │    Queue        │    │ (AI + WebSocket)    │
└─────────────────┘    └─────────────────┘    └─────────────────────┘
        ▲                                              │
        │                                              ▼
┌─────────────────┐                          ┌─────────────────────┐
│     Client      │                          │    WebSocket        │
│   (curl, web)   │◀─────────────────────────│    Updates          │
└─────────────────┘                          └─────────────────────┘
```

### Komponenten:

- **Audio-Gateway**: Flask-Server für MP3/M4A Upload und API-Authentifizierung
- **Transcription-Service**: Kafka Consumer + AI Model + WebSocket Server
- **Kafka**: Message Queue für robuste Job-Verarbeitung
- **WebSocket**: Real-time Status Updates und Ergebnisse

## 🚀 Quick Start

### 1. Installation

```bash
# Repository klonen
git clone <your-repo>
cd audio-transcription-kafka

# Python Environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt
```

## 🔧 Kafka Topic Management

Das System liest alle Kafka-Konfigurationen automatisch aus der `.env` Datei. Du hast mehrere Optionen für das Topic-Management:

### Automatische Topic-Erstellung

**Beim Service-Start (empfohlen):**
```python
# Topics werden automatisch erstellt wenn Services starten
python audio_gateway.py          # Erstellt Topics automatisch
python transcription_service.py  # Nutzt existierende Topics
```

**Via Python-Scripts:**
```bash
# Einfache Methode - nutzt .env Konfiguration
python simple_kafka_setup.py

# Erweiterte Methode mit vielen Optionen
python kafka_topic_creator.py                  # Standard-Topic aus .env
python kafka_topic_creator.py --setup-all      # Alle Projekt-Topics
python kafka_topic_creator.py --list           # Zeige existierende Topics
python kafka_topic_creator.py --show-config    # Zeige .env Konfiguration

# Demo aller verfügbaren Methoden
python demo_kafka_setup.py
```

**Via Config-Klasse (für eigene Scripts):**
```python
from config import Config

# Nur Kafka Topic erstellen
Config.ensure_kafka_topic()

# Alles setup (Upload-Folder + Kafka Topic)
Config.setup_all()
```

### Manuelle Topic-Erstellung

Falls die automatischen Methoden nicht funktionieren:

```bash
# Nutze Werte aus deiner .env Datei:
# KAFKA_BOOTSTRAP_SERVERS=localhost:9092
# KAFKA_TOPIC_AUDIO=audio-transcription

kafka-topics --create \
  --topic audio-transcription \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1
```

### Topic-Konfiguration anpassen

Erweiterte Topic-Konfiguration in der `.env`:

```bash
# Standard Kafka Settings
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_AUDIO=audio-transcription
KAFKA_CONSUMER_GROUP=transcription-workers

# Erweiterte Kafka Settings (optional)
KAFKA_BATCH_SIZE=16384
KAFKA_LINGER_MS=5
KAFKA_COMPRESSION_TYPE=snappy
```

### 3. Konfiguration

Erstelle eine `.env` Datei im Projekt-Root:

```bash
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_AUDIO=audio-transcription
KAFKA_CONSUMER_GROUP=transcription-workers

# API Security
API_KEY=your-super-secret-api-key-here

# File Handling
UPLOAD_FOLDER=/tmp/audio
MAX_CONTENT_LENGTH=104857600  # 100MB

# Services
GATEWAY_HOST=127.0.0.1
GATEWAY_PORT=5000
WEBSOCKET_HOST=127.0.0.1
WEBSOCKET_PORT=8765

# AI Model Configuration
MODEL_ID=openai/whisper-small
GPU_DEVICE=cpu  # oder 'cuda' für GPU

# Optional: Für bessere Performance
# MODEL_ID=openai/whisper-base
# GPU_DEVICE=cuda
```

### 4. Services starten

```bash
# Terminal 1: Audio-Gateway
python audio_gateway.py

# Terminal 2: Transcription-Service
python transcription_service.py
```

Die Services sind bereit wenn du folgende Logs siehst:

```
# Audio-Gateway
INFO - Starting Audio-Gateway on 127.0.0.1:5000
INFO - Kafka Producer connected to localhost:9092

# Transcription-Service  
INFO - Starting Transcription Service...
INFO - Kafka Consumer connected to topic: audio-transcription
INFO - Starting WebSocket server on 127.0.0.1:8765
```

## 📡 API Usage

### Health Check

```bash
curl http://localhost:5000/health
```

**Response:**
```json
{
  "status": "Audio-Gateway is healthy",
  "kafka": "connected"
}
```

### Audio Upload

```bash
# Basic Upload
curl -X POST http://localhost:5000/upload \
  -H "X-API-Key: your-super-secret-api-key-here" \
  -F "file=@your_audio.mp3"
```

**Response:**
```json
{
  "message": "Audio file queued for transcription",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "original_filename": "your_audio.mp3"
}
```

### Status abfragen

```bash
curl http://localhost:5000/status/550e8400-e29b-41d4-a716-446655440000
```

## 🔌 WebSocket Client Beispiele

### JavaScript Browser Client

```javascript
// Verbindung aufbauen
const ws = new WebSocket('ws://localhost:8765');

// Request ID aus Upload Response verwenden
const requestId = "550e8400-e29b-41d4-a716-446655440000";

ws.onopen = function() {
    console.log('WebSocket connected');
    
    // Für Updates zu spezifischem Request anmelden
    ws.send(JSON.stringify({
        type: "join",
        request_id: requestId
    }));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Update received:', data);
    
    switch(data.type) {
        case 'joined':
            console.log(`Listening for updates on ${data.request_id}`);
            break;
            
        case 'transcription_complete':
            console.log('Transcription finished!');
            console.log('Text:', data.result.transcription);
            console.log('Duration:', data.result.audio_duration_minutes, 'minutes');
            console.log('Word count:', data.result.transcription_word_count);
            break;
            
        case 'transcription_error':
            console.error('Transcription failed:', data.error);
            break;
            
        case 'status_update':
            console.log('Service status:', data.data.status);
            break;
    }
};

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};
```

### Python WebSocket Client

```python
import asyncio
import json
import websockets

async def websocket_client(request_id):
    uri = "ws://localhost:8765"
    
    async with websockets.connect(uri) as websocket:
        # Join room for request
        join_message = {
            "type": "join",
            "request_id": request_id
        }
        await websocket.send(json.dumps(join_message))
        
        # Listen for updates
        async for message in websocket:
            data = json.loads(message)
            
            if data.get("type") == "transcription_complete":
                print("✅ Transcription completed!")
                print(f"Text: {data['result']['transcription']}")
                break
            elif data.get("type") == "transcription_error":
                print("❌ Transcription failed!")
                print(f"Error: {data['error']}")
                break
            else:
                print(f"Update: {data}")

# Usage
request_id = "your-request-id-here"
asyncio.run(websocket_client(request_id))
```

### curl für WebSocket (über websocat)

```bash
# Install websocat first: https://github.com/vi/websocat
# Brew: brew install websocat
# Or download binary

# Connect and join room
echo '{"type": "join", "request_id": "your-request-id"}' | websocat ws://localhost:8765

# Get service status
echo '{"type": "get_status"}' | websocat ws://localhost:8765
```

## 🧪 Testing

### Unit Tests

```bash
# Alle Unit Tests
pytest tests/ -v

# Nur spezifische Test-Datei
pytest tests/test_audio_gateway.py -v

# Mit Coverage
pytest tests/ --cov=. --cov-report=html
```

### End-to-End Tests

```bash
# Erster: Stelle sicher, dass beide Services laufen
# Dann E2E Tests ausführen
pytest tests/test_e2e_kafka_transcription.py -v -m e2e

# Oder alle E2E Tests
pytest -m e2e -v
```

### Manuelle Tests

**1. Upload Test:**
```bash
# Test Audio Datei erstellen
echo "test audio content" > test.mp3

# Upload
curl -X POST http://localhost:5000/upload \
  -H "X-API-Key: your-super-secret-api-key-here" \
  -F "file=@test.mp3" \
  | jq .
```

**2. WebSocket Test:**
```bash
# Mit websocat (oder Python script oben)
echo '{"type": "get_status"}' | websocat ws://localhost:8765
```

## 📊 Response Formats

### Successful Transcription Response (WebSocket)

```json
{
  "type": "transcription_complete",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCESS",
  "result": {
    "audio_duration_minutes": 2.34,
    "transcription_word_count": 142,
    "estimated_reading_time_minutes": 0.65,
    "transcription": "Guten Tag, dies ist ein Beispiel für eine Transkription...",
    "prompts": {
      "summary_tasks_and_todos": "Analysiere diesen Text: ``` ... ``` und erstelle...",
      "presentation_structure": "Erstelle aus dem folgenden Text einen Vorschlag...",
      "journalistic_summary": "Versetze dich in die Rolle einer Journalistin..."
    }
  },
  "completed_at": "2025-07-07T14:30:15.123456"
}
```

### Error Response (WebSocket)

```json
{
  "type": "transcription_error", 
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "FAILURE",
  "error": "Audio file is corrupted or unreadable",
  "failed_at": "2025-07-07T14:30:15.123456"
}
```

### Service Status (WebSocket)

```json
{
  "type": "status_update",
  "data": {
    "status": "processing",
    "current_task": {
      "request_id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "audio.mp3",
      "started_at": "2025-07-07T14:30:10"
    },
    "queue_length": 2,
    "uptime_minutes": 45.2,
    "processed_count": 15,
    "error_count": 1
  }
}
```

## 🔧 Troubleshooting

### Häufige Probleme

**1. Kafka Connection Error**
```
ERROR - Failed to connect to Kafka: NoBrokersAvailable
```
**Solution:** 
```bash
# Prüfe .env Konfiguration
python kafka_topic_creator.py --show-config

# Prüfe ob Kafka läuft
kafka-server-start config/server.properties

# Prüfe Kafka-Status
kafka-topics --list --bootstrap-server localhost:9092

# Test Verbindung
python demo_kafka_setup.py
```

**2. .env Datei nicht gefunden/geladen**
```
Warning: python-dotenv not installed. Using defaults.
```
**Solution:**
```bash
# Installiere python-dotenv
pip install python-dotenv

# Prüfe ob .env existiert
ls -la .env

# Erstelle .env falls nicht vorhanden
cp .env.example .env  # oder verwende setup.sh
```

**3. Falsche Kafka-Server Adresse in .env**
```
ERROR - Failed to connect to Kafka at your-server:9092
```
**Solution:**
```bash
# Prüfe aktuelle .env Werte
grep KAFKA .env

# Korrigiere KAFKA_BOOTSTRAP_SERVERS in .env
# Beispiel: KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Teste Konfiguration
python kafka_topic_creator.py --show-config
```

**4. Topic existiert aber mit falschen Settings**
```
Topic 'audio-transcription' already exists
```
**Solution:**
```bash
# Lösche und erstelle Topic neu
python kafka_topic_creator.py --delete audio-transcription
python kafka_topic_creator.py --setup-all

# Oder prüfe existierende Topics
python kafka_topic_creator.py --list
```

**5. WebSocket Connection Refused**
```
Could not connect to WebSocket server at ws://localhost:8765
```
**Solution:**
- Transcription-Service läuft?
- Port 8765 frei? `netstat -an | grep 8765`
- Firewall-Regeln?

**6. AI Model Loading Error**
```
ERROR - Failed to load AI model: No module named 'torch'
```
**Solution:**
```bash
# CPU Version
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# CUDA Version (für GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**7. Permission Denied for Upload Folder**
```
PermissionError: [Errno 13] Permission denied: '/tmp/audio'
```
**Solution:**
```bash
sudo mkdir -p /tmp/audio
sudo chmod 777 /tmp/audio
# Oder anderen Pfad in .env setzen: UPLOAD_FOLDER=./uploads
```

### Logging & Debugging

**Verbose Logging aktivieren:**
```python
# In config.py oder als Environment Variable
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Kafka Messages debuggen:**
```bash
# Consumer für Topic starten (sieht alle Messages)
kafka-console-consumer --topic audio-transcription --from-beginning --bootstrap-server localhost:9092
```

**WebSocket Verbindungen debuggen:**
```bash
# Network tools
netstat -an | grep :8765
lsof -i :8765
```

## ⚡ Performance Tuning

### Kafka Optimierung

```bash
# .env Ergänzungen für bessere Performance
KAFKA_BATCH_SIZE=16384
KAFKA_LINGER_MS=5
KAFKA_COMPRESSION_TYPE=snappy
```

### AI Model Optimierung

```bash
# Für bessere Performance aber mehr Memory
MODEL_ID=openai/whisper-base

# Für GPU (deutlich schneller)
GPU_DEVICE=cuda

# Für Production: größeres Model, bessere Qualität
MODEL_ID=openai/whisper-large-v2
```

### File Handling

```bash
# Größere Uploads erlauben
MAX_CONTENT_LENGTH=524288000  # 500MB

# Parallele Uploads (Audio-Gateway)
FLASK_THREADED=True
```

## 🚀 Production Deployment

### systemd Services

**Audio-Gateway Service (`/etc/systemd/system/audio-gateway.service`):**
```ini
[Unit]
Description=Audio Gateway Service
After=network.target kafka.service

[Service]
Type=simple
User=audiouser
WorkingDirectory=/opt/audio-transcription
ExecStart=/opt/audio-transcription/venv/bin/python audio_gateway.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/audio-transcription

[Install]
WantedBy=multi-user.target
```

**Transcription Service (`/etc/systemd/system/transcription-service.service`):**
```ini
[Unit]
Description=Transcription Service
After=network.target kafka.service audio-gateway.service

[Service]
Type=simple
User=audiouser
WorkingDirectory=/opt/audio-transcription
ExecStart=/opt/audio-transcription/venv/bin/python transcription_service.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/audio-transcription

[Install]
WantedBy=multi-user.target
```

**Services aktivieren:**
```bash
sudo systemctl enable audio-gateway transcription-service
sudo systemctl start audio-gateway transcription-service
sudo systemctl status audio-gateway transcription-service
```

### Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/audio-transcription
server {
    listen 80;
    server_name your-domain.com;

    # Audio Gateway
    location /api/ {
        proxy_pass http://127.0.0.1:5000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket für Transcription Service
    location /ws/ {
        proxy_pass http://127.0.0.1:8765/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## 📈 Monitoring

### Health Checks

```bash
# Script für Monitoring
#!/bin/bash
# health-check.sh

# Audio Gateway
curl -f http://localhost:5000/health || echo "Audio-Gateway DOWN"

# WebSocket (mit timeout)
timeout 5s websocat ws://localhost:8765 <<< '{"type":"get_status"}' || echo "Transcription-Service DOWN"

# Kafka Topic
kafka-topics --list --bootstrap-server localhost:9092 | grep audio-transcription || echo "Kafka Topic MISSING"
```

### Metrics Collection

Für Production könntest du Prometheus Metrics hinzufügen:

```python
# Beispiel in transcription_service.py
from prometheus_client import Counter, Histogram, start_http_server

TRANSCRIPTION_COUNTER = Counter('transcriptions_total', 'Total transcriptions')
TRANSCRIPTION_DURATION = Histogram('transcription_duration_seconds', 'Transcription duration')

# In process_transcription_task():
with TRANSCRIPTION_DURATION.time():
    # ... processing ...
    TRANSCRIPTION_COUNTER.inc()
```

## 📚 Weiterführende Dokumentation

- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Whisper Model Documentation](https://huggingface.co/docs/transformers/model_doc/whisper)
- [WebSocket Protocol RFC](https://tools.ietf.org/html/rfc6455)
- [Flask Documentation](https://flask.palletsprojects.com/)

## 🤝 Contributing

1. Fork das Repository
2. Feature Branch erstellen (`git checkout -b feature/amazing-feature`)
3. Tests schreiben und ausführen
4. Commit (`git commit -m 'Add amazing feature'`)
5. Push to Branch (`git push origin feature/amazing-feature`)
6. Pull Request erstellen

## 📄 License

MIT License - siehe [LICENSE](LICENSE) Datei.

---

**Entwickelt für robuste, skalierbare Audio-Transkription mit Kafka und AI.**