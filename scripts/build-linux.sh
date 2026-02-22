#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade pip
pip install pyinstaller cryptography

rm -rf build dist
pyinstaller --onefile --name whisperstash whisperstash.py

mkdir -p dist/release
cp dist/whisperstash dist/release/whisperstash-linux-x86_64

echo "Built: dist/release/whisperstash-linux-x86_64"
