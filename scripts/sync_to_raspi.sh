#!/bin/bash
#
# Sync AdaptLight to Raspberry Pi
#
# Usage:
#   ./scripts/sync_to_raspi.sh
#   RASPI_HOST=pi@192.168.1.100 ./scripts/sync_to_raspi.sh
#

set -e

# Configuration
RASPI_HOST="${RASPI_HOST:-pi@raspberrypi.local}"
RASPI_PATH="${RASPI_PATH:-/home/pi/adaptlight}"

echo "=============================================="
echo "AdaptLight Sync to Raspberry Pi"
echo "=============================================="
echo "Target: $RASPI_HOST:$RASPI_PATH"
echo ""

# Sync brain library
echo "→ Syncing brain/"
rsync -avz --delete \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    brain/ \
    "$RASPI_HOST:$RASPI_PATH/brain/"

# Sync raspi app (flattened structure)
echo ""
echo "→ Syncing apps/raspi/ as raspi/"
rsync -avz --delete \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    apps/raspi/ \
    "$RASPI_HOST:$RASPI_PATH/raspi/"

# Sync pyproject.toml
echo ""
echo "→ Syncing pyproject.toml"
rsync -avz \
    pyproject.toml \
    "$RASPI_HOST:$RASPI_PATH/"

# Sync run script
echo ""
echo "→ Syncing run.sh"
rsync -avz \
    scripts/run_raspi.sh \
    "$RASPI_HOST:$RASPI_PATH/run.sh"

echo ""
echo "=============================================="
echo "Sync complete!"
echo "=============================================="
echo ""
echo "To run on Raspberry Pi:"
echo "  ssh $RASPI_HOST"
echo "  cd $RASPI_PATH"
echo "  ./run.sh"
echo ""
echo "First-time setup:"
echo "  ssh $RASPI_HOST"
echo "  cd $RASPI_PATH"
echo "  pip install -e ."
echo "  pip install RPi.GPIO rpi_ws281x pyaudio gpiozero pyyaml anthropic openai"
