#!/bin/bash
#
# Run AdaptLight on Raspberry Pi
#
# Usage:
#   ./run.sh
#   ./run.sh --verbose
#   ./run.sh --debug
#

set -e

cd /home/lamp/adaptlight

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Ensure brain is importable
export PYTHONPATH="/home/lamp/adaptlight:$PYTHONPATH"

# Set USB speaker volume (card 2)
/usr/bin/amixer -c 2 sset PCM 85% || echo "Failed to set volume"

# Run the raspi app
python -m raspi.main "$@"
