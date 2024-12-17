#!/bin/bash

# Script to automate wallet generation, dependency installation, and balance checking
set -e

# Configuration
DB_FILE="wallets.db"
DOCKER_IMAGE="planxthanee/ethereum-wallet-generator"
VENV_DIR="venv"
LIMIT=1000
THREADS=8
MODE=2

echo "🚀 Starting the Key Miner Script..."

# Step 1: Check if virtual environment exists, if not create it
if [ ! -d "$VENV_DIR" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv $VENV_DIR
fi

# Step 2: Activate the virtual environment
echo "🟢 Activating virtual environment..."
source $VENV_DIR/bin/activate

# Step 3: Install dependencies
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found. Exiting."
    exit 1
fi
echo "📦 Installing dependencies..."
pip install --quiet -r requirements.txt

# Step 4: Run the Docker wallet generator
echo "⛏️  Generating wallets using Docker..."
docker run --rm -d -v $(pwd):/db $DOCKER_IMAGE \
    -n 0 -limit $LIMIT -db $DB_FILE -c $THREADS -mode $MODE

# Wait for the Docker container to complete
echo "⏳ Monitoring Docker container..."
while [ "$(docker ps -q -f ancestor=$DOCKER_IMAGE)" ]; do
    echo "💤 Wallet generation in progress... checking again in 5 seconds."
    sleep 5
done

# Fixes file ownership issue that docker creates files as root user
sudo chown $USER:$USER wallets.db

echo "✅ Wallet generation completed."

# Step 5: Run the eth-balance.py script
if [ -f "eth-balance.py" ]; then
    echo "💰 Checking wallet balances..."
    python3 eth-balance.py --db $DB_FILE
else
    echo "❌ eth-balance.py script not found. Exiting."
    exit 1
fi

echo "🎉 Process complete! Check the output for results."
