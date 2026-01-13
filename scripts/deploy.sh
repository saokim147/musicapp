#!/bin/bash
# AWS Lightsail Deployment Script for Hum2Song Backend
# Based on docs/deploy.md

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# =============================================================================
# CONFIGURATION
# =============================================================================

# AWS Configuration
INSTANCE_NAME="${INSTANCE_NAME:-hum2song-backend}"
REGION="${REGION:-us-east-1}"
AVAILABILITY_ZONE="${AVAILABILITY_ZONE:-us-east-1a}"
BLUEPRINT_ID="${BLUEPRINT_ID:-ubuntu_22_04}"
BUNDLE_ID="${BUNDLE_ID:-small_3_0}"  # $10/month plan: 1 vCPU, 2 GB RAM, 60 GB SSD

# Local paths (to be copied to server)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_APP_DIR="${PROJECT_ROOT}"

# Remote paths
REMOTE_APP_DIR="/opt/hum2song/app"
REMOTE_VENV_DIR="/opt/hum2song/venv"
SERVICE_FILE="/etc/systemd/system/hum2song.service"

# SSH key
SSH_KEY="${PROJECT_ROOT}/key.pem"
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed. Please install it first."
        exit 1
    fi
}

wait_for_instance() {
    local instance_name="$1"
    local max_attempts=60
    local attempt=1

    log_info "Waiting for instance to be running..."

    while [ $attempt -le $max_attempts ]; do
        state=$(aws lightsail get-instance-state --instance-name "$instance_name" --region "$REGION" --query 'state.name' --output text 2>/dev/null || echo "unknown")

        if [ "$state" = "running" ]; then
            log_success "Instance is running!"
            return 0
        fi

        log_info "Attempt $attempt/$max_attempts: Instance state is '$state'. Waiting..."
        sleep 5
        ((attempt++))
    done

    log_error "Instance did not become running after $max_attempts attempts."
    exit 1
}

wait_for_ssh() {
    local ip_address="$1"
    local max_attempts=60
    local attempt=1

    log_info "Waiting for SSH to be available..."

    while [ $attempt -le $max_attempts ]; do
        if ssh -i "$SSH_KEY" $SSH_OPTS -o ConnectTimeout=5 "ubuntu@${ip_address}" "echo 'SSH is ready'" &> /dev/null; then
            log_success "SSH is ready!"
            return 0
        fi

        log_info "Attempt $attempt/$max_attempts: Waiting for SSH..."
        sleep 5
        ((attempt++))
    done

    log_error "SSH did not become available after $max_attempts attempts."
    exit 1
}

# =============================================================================
# PREREQUISITES CHECK
# =============================================================================

check_prerequisites() {
    log_info "Checking prerequisites..."

    check_command "aws"
    check_command "ssh"
    check_command "scp"

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi

    # Check if instance already exists
    if aws lightsail get-instance --instance-name "$INSTANCE_NAME" --region "$REGION" &> /dev/null; then
        log_warning "Instance '$INSTANCE_NAME' already exists."
        read -p "Do you want to delete it and recreate? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deleting existing instance..."
            aws lightsail delete-instance --instance-name "$INSTANCE_NAME" --region "$REGION"
            sleep 5
        else
            log_info "Using existing instance."
            return 1
        fi
    fi

    log_success "Prerequisites check passed."
    return 0
}

# =============================================================================
# STEP 1: CREATE LIGHTSAIL INSTANCE
# =============================================================================

create_instance() {
    log_info "Step 1: Creating Lightsail instance..."

    aws lightsail create-instances \
        --instance-names "$INSTANCE_NAME" \
        --availability-zone "$AVAILABILITY_ZONE" \
        --blueprint-id "$BLUEPRINT_ID" \
        --bundle-id "$BUNDLE_ID" \
        --region "$REGION" \
        --tags "key=Name,value=$INSTANCE_NAME" "key=Project,value=Hum2Song"

    log_success "Instance creation initiated."

    # Get instance IP
    IP_ADDRESS=$(aws lightsail get-instance --instance-name "$INSTANCE_NAME" --region "$REGION" --query 'instance.publicIpAddress' --output text)

    log_info "Instance IP address: $IP_ADDRESS"

    wait_for_instance "$INSTANCE_NAME"
    wait_for_ssh "$IP_ADDRESS"

    log_success "Instance is ready!"
    echo "$IP_ADDRESS" > /tmp/hum2song_instance_ip.txt
}

# =============================================================================
# STEP 2: CONFIGURE INSTANCE
# =============================================================================

configure_instance() {
    local ip_address="$1"

    log_info "Step 2: Configuring instance..."

    ssh -i "$SSH_KEY" $SSH_OPTS "ubuntu@${ip_address}" << 'ENDSSH'
set -e
echo "=== Updating system packages ==="
sudo apt update && sudo apt upgrade -y

echo "=== Installing system dependencies ==="
sudo apt install -y python3.10 python3.10-venv python3-pip ffmpeg git curl

echo "=== Creating application directory ==="
sudo mkdir -p /opt/hum2song
sudo chown ubuntu:ubuntu /opt/hum2song
ENDSSH

    log_success "Instance configured."
}

# =============================================================================
# STEP 3: SETUP PYTHON ENVIRONMENT
# =============================================================================

setup_python_env() {
    local ip_address="$1"

    log_info "Step 3: Setting up Python environment..."

    ssh -i "$SSH_KEY" $SSH_OPTS "ubuntu@${ip_address}" << 'ENDSSH'
set -e
cd /opt/hum2song

echo "=== Creating virtual environment ==="
python3.10 -m venv venv
source venv/bin/activate

echo "=== Upgrading pip ==="
pip install --upgrade pip

echo "=== Installing PyTorch CPU-only ==="
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

echo "=== Installing FAISS CPU ==="
pip install faiss-cpu

echo "=== Installing other dependencies ==="
pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 \
  python-multipart==0.0.6 pydantic==2.5.0 pydantic-settings==2.1.0 \
  librosa==0.8.0 pydub numpy pandas scikit-learn tqdm

echo "=== Python environment setup complete ==="
ENDSSH

    log_success "Python environment setup complete."
}

# =============================================================================
# STEP 4: DEPLOY APPLICATION CODE
# =============================================================================

deploy_app_code() {
    local ip_address="$1"

    log_info "Step 4: Deploying application code..."

    # Create remote directory structure
    ssh -i "$SSH_KEY" $SSH_OPTS "ubuntu@${ip_address}" "mkdir -p ${REMOTE_APP_DIR}/{backend,audio,models,checkpoints,preprocessed/train,CHAD,config}"

    # Copy application files
    log_info "Copying backend code..."
    scp -i "$SSH_KEY" $SSH_OPTS -r "${LOCAL_APP_DIR}/backend/" "ubuntu@${ip_address}:${REMOTE_APP_DIR}/backend/"

    log_info "Copying audio module..."
    scp -i "$SSH_KEY" $SSH_OPTS -r "${LOCAL_APP_DIR}/audio/" "ubuntu@${ip_address}:${REMOTE_APP_DIR}/audio/"

    log_info "Copying models..."
    scp -i "$SSH_KEY" $SSH_OPTS -r "${LOCAL_APP_DIR}/models/" "ubuntu@${ip_address}:${REMOTE_APP_DIR}/models/"

    log_info "Copying model checkpoint..."
    scp -i "$SSH_KEY" $SSH_OPTS "${LOCAL_APP_DIR}/checkpoints/resnet18_best.pth" "ubuntu@${ip_address}:${REMOTE_APP_DIR}/checkpoints/" 2>/dev/null || \
    scp -i "$SSH_KEY" $SSH_OPTS "${LOCAL_APP_DIR}/checkpoints/resnet18_latest.pth" "ubuntu@${ip_address}:${REMOTE_APP_DIR}/checkpoints/resnet18_best.pth"

    log_info "Copying song embeddings..."
    scp -i "$SSH_KEY" $SSH_OPTS -r "${LOCAL_APP_DIR}/preprocessed/train/song/" "ubuntu@${ip_address}:${REMOTE_APP_DIR}/preprocessed/train/"

    log_info "Copying metadata..."
    scp -i "$SSH_KEY" $SSH_OPTS "${LOCAL_APP_DIR}/preprocessed/train_meta.csv" "ubuntu@${ip_address}:${REMOTE_APP_DIR}/preprocessed/" 2>/dev/null || true

    log_info "Copying song titles..."
    scp -i "$SSH_KEY" $SSH_OPTS "${LOCAL_APP_DIR}/CHAD/group_to_title.csv" "ubuntu@${ip_address}:${REMOTE_APP_DIR}/CHAD/" 2>/dev/null || true

    log_info "Copying config..."
    scp -i "$SSH_KEY" $SSH_OPTS -r "${LOCAL_APP_DIR}/config/" "ubuntu@${ip_address}:${REMOTE_APP_DIR}/config/" 2>/dev/null || true

    log_success "Application code deployed."
}

# =============================================================================
# STEP 5: UPDATE CONFIGURATION
# =============================================================================

update_configuration() {
    local ip_address="$1"

    log_info "Step 5: Updating configuration..."

    ssh -i "$SSH_KEY" $SSH_OPTS "ubuntu@${ip_address}" << ENDSSH
set -e

# Update config.py with server paths
CONFIG_FILE="${REMOTE_APP_DIR}/backend/app/config.py"

if [ -f "\$CONFIG_FILE" ]; then
    echo "=== Updating paths in config.py ==="

    # Backup original
    cp "\$CONFIG_FILE" "\$CONFIG_FILE.bak"

    # Update paths using sed
    sed -i 's|MODEL_CHECKPOINT_PATH:.*|MODEL_CHECKPOINT_PATH: str = "/opt/hum2song/app/checkpoints/resnet18_best.pth"|' "\$CONFIG_FILE"
    sed -i 's|SONGS_NPY_DIR:.*|SONGS_NPY_DIR: str = "/opt/hum2song/app/preprocessed/train/song"|' "\$CONFIG_FILE"
    sed -i 's|METADATA_CSV_PATH:.*|METADATA_CSV_PATH: str = "/opt/hum2song/app/preprocessed/train_meta.csv"|' "\$CONFIG_FILE"
    sed -i 's|SONG_TITLE_CSV_PATH:.*|SONG_TITLE_CSV_PATH: str = "/opt/hum2song/app/CHAD/group_to_title.csv"|' "\$CONFIG_FILE"

    echo "Configuration updated."
else
    echo "Warning: config.py not found at \$CONFIG_FILE"
fi
ENDSSH

    log_success "Configuration updated."
}

# =============================================================================
# STEP 6: CREATE SYSTEMD SERVICE
# =============================================================================

create_systemd_service() {
    local ip_address="$1"

    log_info "Step 6: Creating systemd service..."

    ssh -i "$SSH_KEY" $SSH_OPTS "ubuntu@${ip_address}" << 'ENDSSH'
set -e

echo "=== Creating systemd service file ==="
sudo tee /etc/systemd/system/musicapp.service > /dev/null << 'EOSERVICE'
[Unit]
Description=MusicApp FastAPI Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/musicapp/backend/app
Environment="PATH=/opt/musicapp/.venv/bin"
ExecStart=/opt/musicapp/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOSERVICE

echo "=== Reloading systemd and enabling service ==="
sudo systemctl daemon-reload
sudo systemctl enable musicapp
sudo systemctl start musicapp

echo "=== Waiting for service to start ==="
sleep 5

echo "=== Checking service status ==="
sudo systemctl status musicapp --no-pager
ENDSSH

    log_success "Systemd service created and started."
}

# =============================================================================
# STEP 7: CONFIGURE FIREWALL
# =============================================================================

configure_firewall() {
    local ip_address="$1"

    log_info "Step 7: Configuring firewall..."

    # Open port 8000 using AWS CLI
    aws lightsail open-instance-public-ports \
        --instance-name "$INSTANCE_NAME" \
        --region "$REGION" \
        --port-info fromPort=8000,toPort=8000,protocol=TCP

    log_success "Firewall configured. Port 8000 is now open."
}

# =============================================================================
# STEP 8: VERIFICATION
# =============================================================================

verify_deployment() {
    local ip_address="$1"

    log_info "Step 8: Verifying deployment..."

    # Health check
    log_info "Running health check..."
    sleep 3  # Give service time to fully start

    if health_response=$(curl -s "http://${ip_address}:8000/api/health"); then
        log_success "Health check passed!"
        echo "Response: $health_response"
    else
        log_error "Health check failed!"
        log_info "Service logs:"
        ssh -i "$SSH_KEY" $SSH_OPTS "ubuntu@${ip_address}" "sudo journalctl -u hum2song -n 50 --no-pager"
        return 1
    fi

    # Check logs
    log_info "Checking service logs..."
    ssh -i "$SSH_KEY" $SSH_OPTS "ubuntu@${ip_address}" "sudo journalctl -u hum2song -n 20 --no-pager"

    # Memory check
    log_info "Checking memory usage..."
    ssh -i "$SSH_KEY" $SSH_OPTS "ubuntu@${ip_address}" "free -h"

    log_success "Deployment verification complete!"
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    log_info "=== Hum2Song AWS Lightsail Deployment Script ==="
    log_info "Instance: $INSTANCE_NAME"
    log_info "Region: $REGION"
    log_info ""

    # Check prerequisites
    if check_prerequisites; then
        # Step 1: Create instance
        create_instance
    else
        # Instance already exists, get IP
        IP_ADDRESS=$(aws lightsail get-instance --instance-name "$INSTANCE_NAME" --region "$REGION" --query 'instance.publicIpAddress' --output text)
        echo "$IP_ADDRESS" > /tmp/hum2song_instance_ip.txt
        log_info "Using existing instance with IP: $IP_ADDRESS"
    fi

    IP_ADDRESS=$(cat /tmp/hum2song_instance_ip.txt)

    # Step 2: Configure instance
    configure_instance "$IP_ADDRESS"

    # Step 3: Setup Python environment
    setup_python_env "$IP_ADDRESS"

    # Step 4: Deploy application code
    deploy_app_code "$IP_ADDRESS"

    # Step 5: Update configuration
    update_configuration "$IP_ADDRESS"

    # Step 6: Create systemd service
    create_systemd_service "$IP_ADDRESS"

    # Step 7: Configure firewall
    configure_firewall "$IP_ADDRESS"

    # Step 8: Verify deployment
    verify_deployment "$IP_ADDRESS"

    # Summary
    echo ""
    log_success "=== Deployment Complete! ==="
    echo ""
    echo "Instance Details:"
    echo "  Name: $INSTANCE_NAME"
    echo "  IP Address: $IP_ADDRESS"
    echo "  Region: $REGION"
    echo ""
    echo "Service URLs:"
    echo "  Health Check: http://$IP_ADDRESS:8000/api/health"
    echo "  API Docs: http://$IP_ADDRESS:8000/docs"
    echo "  Search Endpoint: http://$IP_ADDRESS:8000/api/search"
    echo ""
    echo "Useful Commands:"
    echo "  SSH: ssh -i $SSH_KEY ubuntu@$IP_ADDRESS"
    echo "  Service status: ssh -i $SSH_KEY ubuntu@$IP_ADDRESS 'sudo systemctl status hum2song'"
    echo "  View logs: ssh -i $SSH_KEY ubuntu@$IP_ADDRESS 'sudo journalctl -u hum2song -f'"
    echo "  Stop service: ssh -i $SSH_KEY ubuntu@$IP_ADDRESS 'sudo systemctl stop hum2song'"
    echo "  Start service: ssh -i $SSH_KEY ubuntu@$IP_ADDRESS 'sudo systemctl start hum2song'"
    echo ""
    echo "To delete instance:"
    echo "  aws lightsail delete-instance --instance-name $INSTANCE_NAME --region $REGION"
}

# Run main function
main "$@"
