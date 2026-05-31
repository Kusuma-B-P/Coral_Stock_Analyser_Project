#!/bin/bash
set -e

echo "=== Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== Downloading Coral Linux binary ==="
curl -L https://github.com/withcoral/coral/releases/latest/download/coral-x86_64-unknown-linux-musl.zip -o coral.zip
unzip -o coral.zip -d coral-bin
cp coral-bin/coral /usr/local/bin/coral
chmod +x /usr/local/bin/coral

echo "=== Verifying Coral ==="
coral --version

echo "=== Build complete ==="
