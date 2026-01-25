#!/bin/bash
#
# Run AdaptLight on Raspberry Pi
#
# Usage:
#   ./run.sh
#   ./run.sh --verbose
#   ./run.sh --debug
#

cd /home/pi/adaptlight

# Ensure brain is importable
export PYTHONPATH="/home/pi/adaptlight:$PYTHONPATH"

# Run the raspi app
python -m raspi.main "$@"
