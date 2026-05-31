#!/bin/bash
set -e

echo "=== Setting up data directory ==="
mkdir -p data

echo "=== Patching stock_prices.yaml with correct path ==="
DATA_PATH="file://$(pwd)/data/"
sed -i "s|file:///D:/Coral_Project_New/Coral_Project/data/|$DATA_PATH|g" sources/stock_prices.yaml
echo "Path set to: $DATA_PATH"

echo "=== Registering Coral sources ==="
./coral source add --file sources/finnhub.yaml || echo "finnhub already registered"
./coral source add --file sources/sec_edgar.yaml || echo "sec_edgar already registered"
./coral source add --file sources/stock_prices.yaml || echo "stock_prices already registered"
./coral source add --file sources/coingecko.yaml || echo "coingecko already registered"

echo "=== Coral sources registered ==="
./coral source list

echo "=== Starting Streamlit ==="
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --browser.gatherUsageStats false
