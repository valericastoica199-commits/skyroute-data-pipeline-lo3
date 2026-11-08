#!/usr/bin/env bash
# Manual deployment: run the pipeline once on this machine
set -euo pipefail
export SKYROUTE_TRIGGER=manual
python src/pipeline.py --workers 4
