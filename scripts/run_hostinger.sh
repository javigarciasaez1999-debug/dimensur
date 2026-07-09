#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_DIR"

mkdir -p logs data/images data/payloads

exec .venv/bin/python main.py "$@" >> logs/cron.log 2>&1
