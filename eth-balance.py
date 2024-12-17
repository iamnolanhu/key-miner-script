import argparse
import sqlite3
from web3 import Web3
import traceback
import time
import os
from multiprocessing import Process, Lock, Queue
import math

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Update Ethereum wallet balances in a database.')
    parser.add_argument('--db', type=str, required=True,
                        help='Path to the SQLite database file')
    parser.add_argument('--node-list', type=str, default='ETH_NODE_LIST',
                        help='Path to the file containing Ethereum node URLs')
    args = parser.parse_args()
    print(f"Database file provided: {args.db}")
    print(f"Node list file provided: {args.node_list}")

    # Load RPC URLs from the ETH_NODE_LIST file
    if not os.path.isfile(args.node_list):
        print(f"Node list file '{args.node_list}' does not exist.")
        return

    with open(args.node_list, 'r') as f:
        RPC_URLS = [line.strip() for line in f if line.strip()]

    if not RPC_URLS:
        print("No RPC URLs found in the node list file.")
        return

    # Connect to the SQLite database
    print(f"Connecting to database: {args.db}")
    connection = sqlite3.connect(args.db)
    cursor = connection.cursor()

    # Check if 'wallets' table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='wallets';")
    if not cursor.fetchone():
        print("Table 'wallets' does not exist in the database.")
        connection.close()
        return

    # Add a 'balance' column to the table if it doesn't already exist
    cursor.execute("PRAGMA table_info(wallets)")
    columns = [column[1] for column in cursor.fetchall()]
    print(f"Columns in 'wallets' table: {columns}")

    if "balance" not in columns:
        cursor.execute("ALTER TABLE wallets ADD COLUMN balance REAL")
        connection.commit()
        print("Added 'balance' column to the wallets table.")

    # Fetch wallet addresses from the database
    cursor.execute("SELECT address FROM wallets")
    wallets = [address[0].strip() for address in cursor.fetchall()]
    connection.close()

    if not wallets:
        print("No wallet addresses found in the 'wallets' table.")
        return
    else:
        print(f"Found {len(wallets)} wallet(s) to process.")

    # Split wallets among processes
    num_processes = min(len(RPC_URLS), len(wallets))
    wallets_per_process = math.ceil(len(wallets) / num_processes)
    wallet_chunks = [wallets[i:i + wallets_per_process] for i in range(0, len(wallets), wallets_per_process)]

    # Create a Lock for database access
    db_lock = Lock()

    # Create a Queue to collect results
    result_queue = Queue()

    processes = []
    for idx, rpc_url in enumerate(RPC_URLS[:num_processes]):
        wallet_subset = wallet_chunks[idx]
        p = Process(target=process_wallets_parallel, args=(
            args.db, rpc_url, wallet_subset, db_lock, result_queue))
        processes.append(p)
        p.start()

    # Wait for all processes to finish
    for p in processes:
        p.join()

    # Retrieve results from the queue
    while not result_queue.empty():
        result = result_queue.get()
        if result['status'] == 'failed':
            print(f"Process with RPC URL {result['rpc_url']} failed after maximum retries.")

    print("\nProcessing completed.")

def process_wallets_parallel(db_file, rpc_url, wallets, db_lock, result_queue):
    MAX_RETRIES = 3
    retry_count = 0
    success = False

    while retry_count < MAX_RETRIES and not success:
        try:
            print(f"\nProcess PID {os.getpid()} connecting using RPC URL: {rpc_url}")

            # Connect to the Ethereum blockchain
            w3 = Web3(Web3.HTTPProvider(rpc_url))

            # Attempt to validate the connection
            if not w3.is_connected():
                raise ConnectionError("Failed to connect to the Ethereum node.")

            client_version = w3.client_version
            print(f"Connected to Ethereum node: {client_version}")

            # Process wallets
            for original_address in wallets:
                print(f"Process PID {os.getpid()} processing address: {original_address}")
                if Web3.is_address(original_address):
                    try:
                        # Convert to checksum address
                        checksummed_address = Web3.to_checksum_address(original_address)
                        print(f"Checksum address: {checksummed_address}")

                        # Get balance using the checksum address
                        balance = w3.eth.get_balance(checksummed_address)  # Get balance in Wei

                        # Convert balance from Wei to Ether
                        eth_balance = float(Web3.from_wei(balance, 'ether'))

                        # Update balance in the database
                        with db_lock:
                            connection = sqlite3.connect(db_file)
                            cursor = connection.cursor()
                            cursor.execute(
                                "UPDATE wallets SET balance = ? WHERE address = ?", (eth_balance, original_address))
                            connection.commit()
                            connection.close()

                        print(
                            f"Updated: Address: {original_address} | Balance: {eth_balance} ETH")

                    except Exception as e:
                        print(f"Error retrieving balance for address {original_address}: {e}")
                        raise  # Re-raise exception to trigger retry
                else:
                    print(f"Invalid address: {original_address}")

            success = True  # Set success flag if processing completes without exceptions

        except Exception as e:
            retry_count += 1
            print(f"Process PID {os.getpid()} error on attempt {retry_count}: {e}")
            traceback.print_exc()
            if retry_count < MAX_RETRIES:
                print(f"Process PID {os.getpid()} retrying...")
                time.sleep(1)  # Optional delay before retrying
            else:
                print(f"Process PID {os.getpid()} reached maximum retries.")
                result = {
                    'rpc_url': rpc_url,
                    'status': 'failed'
                }
                result_queue.put(result)
                return  # Exit the process gracefully

    if success:
        result = {
            'rpc_url': rpc_url,
            'status': 'success'
        }
        result_queue.put(result)

if __name__ == "__main__":
    main()