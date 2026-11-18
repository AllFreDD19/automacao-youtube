#!/usr/bin/env bash
# Mesmo que o rodar.bat, para o Linux (Claude Code na nuvem): ./rodar.sh <comando> ...
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then exec .venv/bin/python main.py "$@"; fi
exec python3 main.py "$@"
