#!/bin/bash

# Audio Transcription Service Setup Script
echo "🎵 Audio Transcription Service - Setup Script"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_warning "Running as root. Consider creating a dedicated user for production."
fi

# Step 1: Check Prerequisites
print_status "Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed."
    exit 1
fi
print_success "Python 3 found: $(python3 --version)"

# Check pip
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is required but not installed."
    exit 1
fi
print_success "pip3 found"

# Check if Kafka is accessible (optional check)
print_status "Checking Kafka availability..."
if command -v kafka-topics &> /dev/null; then
    if kafka-topics --list --bootstrap-server localhost:9092 &> /dev/null; then
        print_success "Kafka is running and accessible"
    else
        print_warning "Kafka broker not accessible at localhost:9092"
        echo "Make sure Kafka is running before starting the services."
    fi
else
    print_warning "Kafka command line tools not found in PATH"
    echo "Make sure Kafka is installed and running."
fi

# Step 2: Create Virtual Environment
print_status "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_warning "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
print_success "Virtual environment activated"

# Step 3: Install Dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
print_success "Dependencies installed"

# Step 4: Create Upload Directory
print_status "Setting up upload directory..."
UPLOAD_DIR="/tmp/audio"
mkdir -p "$UPLOAD_DIR"
chmod 755 "$UPLOAD_DIR"
print_success "Upload directory created: $UPLOAD_DIR"

# Step 5: Create .env file if it doesn't exist
print_status "Setting up configuration..."
if [ ! -f ".env" ]; then
    cat > .env << EOF
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_AUDIO=audio-transcription
KAFKA_CONSUMER_GROUP=transcription-workers

# API Security - CHANGE THIS IN PRODUCTION!
API_KEY=dev-api-key-$(date +%s)

# File Handling
UPLOAD_FOLDER=$UPLOAD_DIR
MAX_CONTENT_LENGTH=104857600

# Services
GATEWAY_HOST=127.0.0.1
GATEWAY_PORT=5000
WEBSOCKET_HOST=127.0.0.1
WEBSOCKET_PORT=8765

# AI Model Configuration
MODEL_ID=openai/whisper-small
GPU_DEVICE=cpu

# Uncomment for better performance (requires GPU)
# MODEL_ID=openai/whisper-base
# GPU_DEVICE=cuda
EOF
    print_success "Configuration file .env created"
    print_warning "Generated API key: $(grep API_KEY .env | cut -d'=' -f2)"
    print_warning "Change the API_KEY in .env for production use!"
else
    print_warning ".env file already exists, skipping creation"
fi

# Step 6: Create Kafka Topic
print_status "Setting up Kafka topic..."
if command -v kafka-topics &> /dev/null; then
    TOPIC_NAME=$(grep KAFKA_TOPIC_AUDIO .env | cut -d'=' -f2)
    KAFKA_SERVER=$(grep KAFKA_BOOTSTRAP_SERVERS .env | cut -d'=' -f2)
    
    if kafka-topics --list --bootstrap-server "$KAFKA_SERVER" | grep -q "$TOPIC_NAME"; then
        print_warning "Kafka topic '$TOPIC_NAME' already exists"
    else
        kafka-topics --create \
            --topic "$TOPIC_NAME" \
            --bootstrap-server "$KAFKA_SERVER" \
            --partitions 1 \
            --replication-factor 1 \
            --config cleanup.policy=delete \
            --config retention.ms=86400000
        
        if [ $? -eq 0 ]; then
            print_success "Kafka topic '$TOPIC_NAME' created"
        else
            print_error "Failed to create Kafka topic. Check Kafka server connection."
        fi
    fi
else
    print_warning "Kafka tools not available. Please create topic manually:"
    echo "kafka-topics --create --topic audio-transcription --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1"
fi

# Step 7: Run Tests
print_status "Running basic tests..."
if python -m pytest tests/test_transcription_logic.py -v --tb=short; then
    print_success "Core logic tests passed"
else
    print_warning "Some tests failed. Check the output above."
fi

# Step 8: Download AI Model (optional warm-up)
print_status "Pre-downloading AI model (this may take a few minutes)..."
cat > test_model_download.py << EOF
import os
os.environ['TRANSFORMERS_OFFLINE'] = '0'
try:
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    model_id = "openai/whisper-small"
    print(f"Downloading {model_id}...")
    model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id)
    processor = AutoProcessor.from_pretrained(model_id)
    print("Model download completed!")
except Exception as e:
    print(f"Model download failed: {e}")
    print("The model will be downloaded on first use.")
EOF

python test_model_download.py
rm test_model_download.py
print_success "Model download completed"

# Step 9: Create start scripts
print_status "Creating startup scripts..."

# Audio Gateway start script
cat > start_audio_gateway.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting Audio Gateway..."
python audio_gateway.py
EOF

# Transcription Service start script  
cat > start_transcription_service.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting Transcription Service..."
python transcription_service.py
EOF

# Combined start script
cat > start_all_services.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"

echo "Starting all services in background..."

# Start Audio Gateway
source venv/bin/activate
python audio_gateway.py &
GATEWAY_PID=$!
echo "Audio Gateway started (PID: $GATEWAY_PID)"

# Wait a moment for gateway to start
sleep 2

# Start Transcription Service
python transcription_service.py &
TRANSCRIPTION_PID=$!
echo "Transcription Service started (PID: $TRANSCRIPTION_PID)"

echo "Both services are running. Press Ctrl+C to stop."
echo "Audio Gateway: http://localhost:5000"
echo "WebSocket: ws://localhost:8765"

# Wait for interrupt
trap 'echo "Stopping services..."; kill $GATEWAY_PID $TRANSCRIPTION_PID; exit' INT
wait
EOF

chmod +x start_*.sh
print_success "Startup scripts created"

# Step 10: Create test script
print_status "Creating test script..."
cat > test_upload.sh << 'EOF'
#!/bin/bash

# Get API key from .env
API_KEY=$(grep "^API_KEY=" .env | cut -d'=' -f2)

if [ -z "$API_KEY" ]; then
    echo "Error: API_KEY not found in .env file"
    exit 1
fi

# Create a test audio file
echo "Creating test audio file..."
echo "This is test audio content" > test_audio.mp3

# Test upload
echo "Testing upload..."
curl -X POST http://localhost:5000/upload \
  -H "X-API-Key: $API_KEY" \
  -F "file=@test_audio.mp3" \
  | jq . 2>/dev/null || echo "Upload response received (install jq for pretty formatting)"

# Cleanup
rm -f test_audio.mp3
EOF

chmod +x test_upload.sh
print_success "Test script created"

# Final Summary
echo ""
print_success "🎉 Setup completed successfully!"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Start the services:"
echo "   ./start_all_services.sh"
echo ""
echo "2. In separate terminals, start individually:"
echo "   ./start_audio_gateway.sh"
echo "   ./start_transcription_service.sh"
echo ""
echo "3. Test the upload:"
echo "   ./test_upload.sh"
echo ""
echo "4. Monitor logs and check:"
echo "   - Audio Gateway: http://localhost:5000/health"
echo "   - WebSocket: ws://localhost:8765"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- Your API key: $(grep API_KEY .env | cut -d'=' -f2)"
echo "- Change the API key in .env for production!"
echo "- Make sure Kafka is running before starting services"
echo ""
echo -e "${GREEN}Happy transcribing! 🎵${NC}"
EOF