#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .
printf '\nStart GUI: .venv/bin/easyecg gui\nCLI: .venv/bin/easyecg run INPUT.zip -o OUTPUT\n'
