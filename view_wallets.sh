#!/bin/bash

# Check if the database file is provided
if [ -z "$1" ]; then
    echo "Usage: ./view_wallets.sh <database_file>"
    exit 1
fi

DB_FILE=$1

# Check if the file exists
if [ ! -f "$DB_FILE" ]; then
    echo "Error: File '$DB_FILE' not found!"
    exit 1
fi

# Confirm the file is an SQLite database
if ! file "$DB_FILE" | grep -q "SQLite"; then
    echo "Error: '$DB_FILE' is not an SQLite database."
    exit 1
fi

# Set a fixed column width
COL_WIDTH=19

# Check if 'wallets' table exists
WALLETS_EXIST=$(sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name='wallets';")

if [ "$WALLETS_EXIST" == "wallets" ]; then
    echo -e "\n=== Displaying data from the 'wallets' table (truncated view) ==="
    sqlite3 "$DB_FILE" <<EOF
.headers on
.mode column --wrap 0
SELECT 
    address, 
    private_key,
    substr(created_at, 1, $COL_WIDTH) AS created_at,
    substr(updated_at, 1, $COL_WIDTH) AS updated_at,
    substr(balance, 1, 10) AS balance
FROM wallets;
EOF
else
    echo -e "\nTable 'wallets' not found in the database."
fi