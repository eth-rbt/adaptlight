#!/bin/bash
# Sync AdaptLight files to Raspberry Pi
# Usage: ./sync-to-pi.sh [IP_ADDRESS]

# Configuration
PI_IP="${1:-192.168.1.100}"  # Use first argument or default
PI_USER="pi"
PI_PATH="~/adaptlight"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "AdaptLight Sync to Raspberry Pi"
echo "=========================================="
echo ""

# Check if IP is provided
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}No IP address provided. Using default: $PI_IP${NC}"
    echo "Usage: ./sync-to-pi.sh <raspberry_pi_ip>"
    echo ""
    read -p "Continue with $PI_IP? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Check if worktree/raspi exists
if [ ! -d "worktree/raspi" ]; then
    echo -e "${RED}Error: worktree/raspi directory not found!${NC}"
    echo "Run this script from the adaptlight root directory."
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found!${NC}"
    echo "The Raspberry Pi will need an .env file with OPENAI_API_KEY"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Test connection
echo -e "${YELLOW}Testing connection to $PI_IP...${NC}"
if ! ping -c 1 -W 2 $PI_IP > /dev/null 2>&1; then
    echo -e "${RED}Error: Cannot reach $PI_IP${NC}"
    echo "Make sure:"
    echo "  1. Raspberry Pi is powered on"
    echo "  2. Connected to same network"
    echo "  3. SSH is enabled on Pi"
    exit 1
fi
echo -e "${GREEN}✓ Connection successful${NC}"
echo ""

# Sync raspi folder
echo -e "${YELLOW}Syncing raspi folder to $PI_USER@$PI_IP:$PI_PATH${NC}"
echo ""

rsync -avz --progress \
  --exclude '*.pyc' \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  --exclude 'test_recording.wav' \
  --exclude 'temp_recording.wav' \
  --exclude 'venv/' \
  --exclude '.git/' \
  worktree/raspi/ $PI_USER@$PI_IP:$PI_PATH/

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Files synced successfully${NC}"
else
    echo ""
    echo -e "${RED}✗ Sync failed${NC}"
    exit 1
fi

# Sync .env file if it exists
if [ -f ".env" ]; then
    echo ""
    echo -e "${YELLOW}Syncing .env file...${NC}"
    rsync -avz --progress .env $PI_USER@$PI_IP:~/

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ .env file synced${NC}"
    else
        echo -e "${YELLOW}⚠ .env sync failed (you may need to create it manually)${NC}"
    fi
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Sync Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. SSH into Raspberry Pi:"
echo "     ssh $PI_USER@$PI_IP"
echo ""
echo "  2. Install dependencies (first time only):"
echo "     cd ~/adaptlight"
echo "     pip3 install -r requirements.txt"
echo ""
echo "  3. Test hardware:"
echo "     sudo python3 test_leds.py"
echo ""
echo "  4. Run main application:"
echo "     sudo python3 main.py"
echo ""
echo "  5. Or restart service (if configured):"
echo "     sudo systemctl restart adaptlight.service"
echo ""
