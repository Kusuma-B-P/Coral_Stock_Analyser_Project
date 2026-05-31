#!/bin/bash
set -e

echo "=== Installing Python dependencies ==="
pip install --no-cache-dir -r requirements.txt

echo "=== Downloading Coral Linux binary ==="
curl -L --retry 3 \
  https://github.com/withcoral/coral/releases/download/v0.4.1/coral-x86_64-unknown-linux-gnu.tar.gz \
  -o /tmp/coral.tar.gz

tar -xzf /tmp/coral.tar.gz -C /tmp/
cp /tmp/coral ./coral
chmod +x ./coral
rm -f /tmp/coral.tar.gz

echo "=== Verifying Coral ==="
./coral --version

echo "=== Build complete ==="
