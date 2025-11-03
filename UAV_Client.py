import airsim
import json
import time 
import hashlib
import os
import sys
import datetime
import socket

# ============================================================================
# UAV BLOCKCHAIN AUTHENTICATION CLIENT WITH EPOH (Enhanced Proof of History)
# ============================================================================
# Author: Muntasir-Mamun7
# Date: 2025-10-25
# Purpose: Secure UAV authentication and flight logging using blockchain PoH
# ============================================================================

# --- Configuration (CRITICAL) ---
AIRSIM_HOST_IP = "192.168.43.231"  # Windows Host IP for AirSim
API_HOST = '127.0.0.1'              # The GCS_LeaderNode.py API host
API_PORT = 5000                     # The GCS_LeaderNode.py API port

UAV_SUPI = 'UAV_A1'                 # UAV Subscriber Permanent Identifier
LONG_TERM_KEY = 'K_LongTerm_A1'     # Long-term authentication key

LEDGER_FILE = 'epoh_ledger.json'    # Live blockchain ledger
ARCHIVE_DIR = 'flight_archives'     # Archived flight logs directory
COUNT_FILE = 'flight_count.txt'     # Flight counter
UAV_DB = {'UAV_A1': 'K_LongTerm_A1', 'UAV_B2': 'K_LongTerm_B2'}
# -----------------------------------

# =============================================================================
# SECTION 1: CORE BLOCKCHAIN & CRYPTOGRAPHIC FUNCTIONS
# =============================================================================

def hash_block(block):
    """
    Calculates the SHA-256 hash of a block for blockchain linking.
    This is the STANDARD hash function used for verification.
    
    Args:
        block (dict): Block dictionary containing blockchain data
        
    Returns:
        str: Hexadecimal SHA-256 hash of the block
    """
    temp_block = block.copy()
    if 'current_hash' in temp_block:
        del temp_block['current_hash']
    # CRITICAL: Use separators to remove whitespace (consistent with verification)
    block_string = json.dumps(temp_block, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(block_string.encode()).hexdigest()

def calculate_session_key_simulated(long_term_key, rand):
    """
    Simulates the derivation of the Session Key (KTx).
    In production, this would use a proper key derivation function (KDF).
    
    Args:
        long_term_key (str): Long-term authentication key
        rand (int): Random challenge value
        
    Returns:
        str: Derived session key (first 16 hex characters)
    """
    combined = (long_term_key + str(rand)).encode('utf-8')
    return hashlib.sha256(combined).hexdigest()[:16]

def generate_auth_vector_simulated(uav_supi, long_term_key):
    """
    Simulates the Ground Control Station (GCS) generating an Authentication Vector (AV).
    Based on 5G-AKA authentication protocol.
    
    Args:
        uav_supi (str): UAV Subscriber Permanent Identifier
        long_term_key (str): Long-term authentication key
        
    Returns:
        tuple: (rand, autn, xres_star, ktx) - Authentication vector components
    """
    rand = int(time.time() * 1000)  # Random challenge based on timestamp
    
    # Generate AUTN (Authentication Token)
    autn_data = (long_term_key + uav_supi + str(rand)).encode('utf-8')
    autn = hashlib.sha256(autn_data).hexdigest()
    
    # Generate XRES* (Expected Response)
    xres_data = (long_term_key + str(rand) + 'Expected').encode('utf-8')
    xres_star = hashlib.sha256(xres_data).hexdigest()[:10]
    
    # Generate session key
    ktx = calculate_session_key_simulated(long_term_key, rand)
    
    return rand, autn, xres_star, ktx

def calculate_res_star_simulated(long_term_key, rand):
    """
    Calculates the UAV's response (RES*) to an authentication challenge.
    
    Args:
        long_term_key (str): Long-term authentication key
        rand (int): Random challenge value
        
    Returns:
        str: Response value (first 10 hex characters)
    """
    xres_data = (long_term_key + str(rand) + 'Expected').encode('utf-8')
    return hashlib.sha256(xres_data).hexdigest()[:10]

# =============================================================================
# SECTION 2: FLIGHT ARCHIVING & FILE MANAGEMENT
# =============================================================================

def get_next_flight_number():
    """
    Reads and increments the flight count for sequential flight numbering.
    
    Returns:
        int: Next available flight number
    """
    if not os.path.exists(ARCHIVE_DIR): 
        os.makedirs(ARCHIVE_DIR)
    
    if not os.path.exists(COUNT_FILE):
        next_id = 0
    else:
        try:
            with open(COUNT_FILE, 'r') as f:
                next_id = int(f.read().strip()) + 1
        except:
            next_id = 0
    
    with open(COUNT_FILE, 'w') as f:
        f.write(str(next_id))
    
    return next_id

def archive_current_ledger(flight_id):
    """
    Archives the current flight's blockchain ledger to permanent storage.
    
    Args:
        flight_id (int): Flight identifier number
        
    Returns:
        str or None: Archive filename if successful, None otherwise
    """
    if os.path.exists(LEDGER_FILE) and os.path.getsize(LEDGER_FILE) > 1000:
        archive_name = f"Flight_{flight_id}.json"
        archive_path = os.path.join(ARCHIVE_DIR, archive_name)
        
        try:
            # Move the file from the live ledger to the archive folder
            os.rename(LEDGER_FILE, archive_path)
            print(f"📦 Archiver: Successfully archived log as {archive_name}")
            return archive_name
        except Exception as e:
            print(f"❌ Archiver: FAILED to save ledger. Details: {e}")
            return None
    return None

# =============================================================================
# SECTION 3: EPOH (ENHANCED PROOF OF HISTORY) CORE ENGINE
# =============================================================================

class EPOH_Core:
    """
    Enhanced Proof of History (EPOH) Core Engine.
    
    Implements a hybrid PoH system that:
    1. Uses sequential hashing for temporal ordering (in event logs)
    2. Uses standard hash_block() for blockchain linking (for verification)
    
    This ensures both PoH benefits AND reliable verification.
    """
    
    def __init__(self, difficulty=2):
        """
        Initialize the EPOH core engine.
        
        Args:
            difficulty (int): Number of sequential hashes per transaction
        """
        self.difficulty = difficulty
        self.latest_hash = '0' * 64
        self.sequence_count = 0
        
    def generate_sequential_hash(self):
        """
        Generates the next hash in the PoH sequence.
        This creates a verifiable delay function (VDF).
        
        Returns:
            str: Next sequential hash
        """
        data = self.latest_hash.encode('utf-8')
        new_hash = hashlib.sha256(data).hexdigest()
        self.latest_hash = new_hash
        self.sequence_count += 1
        return new_hash
        
    def embed_transaction(self, data_payload):
        """
        Embeds a transaction into the PoH sequence.
        This proves the transaction occurred at a specific point in time.
        
        Args:
            data_payload (dict): Transaction data to embed
            
        Returns:
            tuple: (timestamp, hash_at_event)
        """
        # CRITICAL: Use separators to remove whitespace
        data_string = json.dumps(data_payload, sort_keys=True, separators=(',', ':'))
        combined_data = (self.latest_hash + data_string).encode('utf-8')
        self.latest_hash = hashlib.sha256(combined_data).hexdigest()
        self.sequence_count += 1
        return time.time(), self.latest_hash
        
    def create_block(self, transactions, previous_hash, current_chain_length, flight_id):
        """
        Creates a new blockchain block with EPOH temporal proofs.
        
        HYBRID APPROACH (BEST PRACTICE):
        - Event logs use EPOH sequential hashing (temporal proofs)
        - Block linking uses standard hash_block() (verification consistency)
        
        Args:
            transactions (list): List of transactions to include
            previous_hash (str): Hash of the previous block
            current_chain_length (int): Current length of the chain
            flight_id (int): Flight identifier
            
        Returns:
            dict: Complete block structure
        """
        self.latest_hash = previous_hash
        self.sequence_count = 0
        event_log = []
        
        # Process each transaction with PoH
        for tx in transactions:
            # Generate sequential hashes (VDF - Verifiable Delay Function)
            for _ in range(self.difficulty): 
                self.generate_sequential_hash()
            
            # Embed the transaction into PoH sequence
            tx_time, tx_hash = self.embed_transaction(tx)
            
            # Record the event with temporal proof
            event_log.append({
                'event_type': 'TRANSACTION_EMBEDDED', 
                'timestamp': tx_time, 
                'hash_at_event': tx_hash,  # PoH hash (temporal proof)
                'tx_id': tx.get('tx_id'), 
                'flight_id': flight_id
            })
            
        # Build the block structure
        final_block = {
            'index': current_chain_length + 1, 
            'timestamp': time.time(),
            'previous_hash': previous_hash, 
            'event_log': event_log,
            'transactions': transactions
        }
        
        # CRITICAL: Use standard hash_block() for blockchain linking
        # This ensures verification consistency across Python and JavaScript
        final_block['current_hash'] = hash_block(final_block)
        
        # Update EPOH state for continuity
        self.latest_hash = final_block['current_hash']
        
        return final_block

# =============================================================================
# SECTION 4: LOCAL LEADER NODE (FLIGHT BLOCKCHAIN MANAGER)
# =============================================================================

class LeaderNodeLocal:
    """
    Local Leader Node - Manages blockchain for a single UAV flight.
    
    Responsibilities:
    - Genesis block creation
    - Authentication transaction processing
    - Telemetry data logging
    - Block mining with EPOH
    - Chain persistence
    """
    
    def __init__(self, flight_id):
        """
        Initialize the local leader node for a flight.
        
        Args:
            flight_id (int): Unique flight identifier
        """
        self.flight_id = flight_id
        self.chain = []
        self.transaction_pool = []
        self.pending_auth_challenges = {}
        self.epoh = EPOH_Core(difficulty=2)
        self.create_genesis_block()

    def save_chain(self):
        """
        Persists the blockchain to disk.
        """
        with open(LEDGER_FILE, 'w') as f:
            json.dump(self.chain, f, indent=4)

    def create_genesis_block(self):
        """
        Creates the genesis block (Block #0) for the flight.
        This is the first block in the chain and establishes the initial state.
        """
        genesis_block = {
            'index': 0, 
            'timestamp': time.time(), 
            'previous_hash': '0',
            'event_log': [{'event_type': 'CHAIN_START', 'flight_id': self.flight_id}],
            'transactions': [{'tx_id': 'GENESIS_TX', 'data': f'Flight {self.flight_id} Initialized'}]
        }
        
        # CRITICAL: Use standard hash_block() for consistency
        genesis_block['current_hash'] = hash_block(genesis_block)
        
        # Update EPOH state to match
        self.epoh.latest_hash = genesis_block['current_hash']
        
        self.chain.append(genesis_block)
        self.save_chain()
        print(f"⛓️  LeaderNode: Genesis Block Created for Flight {self.flight_id}.")

    def mine_block(self):
        """
        Mines a new block from the transaction pool using EPOH.
        
        Returns:
            str or None: Hash of the new block if successful, None if pool empty
        """
        if not self.transaction_pool: 
            return None
            
        last_hash = self.chain[-1]['current_hash']
        
        # Create block with EPOH temporal proofs
        new_block = self.epoh.create_block(
            self.transaction_pool, 
            last_hash, 
            len(self.chain), 
            self.flight_id
        )
        
        self.chain.append(new_block)
        self.save_chain()
        print(f"⛏️  LeaderNode: ✅ EPOH Block #{new_block['index']} Mined.")
        
        self.transaction_pool = []
        return new_block['current_hash']

    def handle_auth_request_1(self, uav_supi):
        """
        Handles UAV authentication request - Step 1: Challenge Generation.
        Based on 5G-AKA protocol.
        
        Args:
            uav_supi (str): UAV Subscriber Permanent Identifier
            
        Returns:
            dict: Authentication challenge containing RAND and AUTN
        """
        long_term_key = UAV_DB[uav_supi]
        rand, autn, xres_star, ktx = generate_auth_vector_simulated(uav_supi, long_term_key)
        
        # Store pending challenge for verification
        self.pending_auth_challenges[uav_supi] = {
            'xres_star': xres_star, 
            'ktx_sim': ktx, 
            'rand': rand
        }
        
        return {
            'status': 'CHALLENGE_ISSUED', 
            'rand': rand, 
            'autn': autn, 
            'pk_node': 'NodePubKey_Sim'
        }

    def handle_auth_response_2(self, uav_supi, res_star_received):
        """
        Handles UAV authentication response - Step 2: Response Verification.
        
        Args:
            uav_supi (str): UAV Subscriber Permanent Identifier
            res_star_received (str): Response from UAV
            
        Returns:
            dict: Authentication result with session key if successful
        """
        pending_challenge = self.pending_auth_challenges.get(uav_supi)
        
        if pending_challenge and res_star_received == pending_challenge['xres_star']:
            session_key = pending_challenge['ktx_sim']
            
            # Create authentication success transaction
            success_tx = {
                'tx_id': f'AUTH_SUCCESS_{uav_supi}_{int(time.time())}',
                'uav_supi': uav_supi, 
                'status': 'AUTHENTICATED',
                'session_key_sim': session_key, 
                'auth_rand': pending_challenge['rand']
            }
            
            self.transaction_pool.append(success_tx)
            del self.pending_auth_challenges[uav_supi]
            
            # Mine block with authentication transaction
            self.mine_block()
            
            return {'status': 'AUTH_SUCCESS', 'session_key': session_key}
        else:
            return {'status': 'AUTH_FAILURE', 'reason': 'RES* mismatch or no pending challenge'}
            
    def handle_telemetry_tx(self, telemetry_tx):
        """
        Handles telemetry data transaction.
        
        Args:
            telemetry_tx (dict): Telemetry transaction data
            
        Returns:
            dict: Transaction receipt
        """
        self.transaction_pool.append(telemetry_tx)
        
        # Mine block when pool reaches threshold (batching)
        if len(self.transaction_pool) >= 3:
            current_hash = self.mine_block()
            return {'status': 'TX_BLOCK_ACK', 'hash': current_hash[:10]}
        else:
            return {'status': 'TX_RECEIVED'}

# =============================================================================
# SECTION 5: UAV FLIGHT CONTROL & DATA COLLECTION
# =============================================================================

def get_telemetry_data(client):
    """
    Fetches key telemetry data from AirSim.
    
    Args:
        client: AirSim MultirotorClient instance
        
    Returns:
        dict: Telemetry data including position and velocity
    """
    state = client.getMultirotorState()
    pos = state.kinematics_estimated.position
    vel = state.kinematics_estimated.linear_velocity
    
    telemetry = {
        'x_pos': round(pos.x_val, 3),
        'y_pos': round(pos.y_val, 3),
        'z_alt': round(pos.z_val, 3), 
        'vel_mag': round((vel.x_val**2 + vel.y_val**2 + vel.z_val**2)**0.5, 3)
    }
    return telemetry

# =============================================================================
# SECTION 6: MAIN FLIGHT EXECUTION & ARCHIVING
# =============================================================================

def run_uav_archiver():
    """
    Main flight execution function.
    
    Flight Phases:
    1. Initialization & Genesis Block
    2. AirSim Connection & Takeoff
    3. Authentication Handshake
    4. Flight Path Execution with Telemetry Logging
    5. Landing & Log Archiving
    """
    
    # --- PHASE 1: FLIGHT INITIALIZATION ---
    print("\n" + "="*70)
    print("🚁 UAV BLOCKCHAIN AUTHENTICATION & LOGGING SYSTEM")
    print("="*70)
    
    current_flight_id = get_next_flight_number()
    print(f"📋 Flight ID: {current_flight_id}")
    print(f"🔐 UAV SUPI: {UAV_SUPI}")
    
    local_leader_node = LeaderNodeLocal(current_flight_id)
    
    airsim_client = None
    session_key = None
    
    # --- PHASE 2: AIRSIM CONNECTION AND TAKEOFF ---
    print("\n--- Phase 2: AirSim Connection ---")
    try:
        airsim_client = airsim.MultirotorClient(ip=AIRSIM_HOST_IP)
        airsim_client.confirmConnection()
        print("✅ AirSim API Connection Confirmed.")
        
        print("⏳ Awaiting full PX4 link (3s delay)...")
        time.sleep(3) 
        
        airsim_client.enableApiControl(True)
        airsim_client.armDisarm(True)
        print("🔓 UAV Armed")
        
        airsim_client.takeoffAsync(timeout_sec=5).join()
        airsim_client.moveToZAsync(-10, 5).join()
        print("🛫 UAV Took Off to 10m altitude.")
        
    except Exception as e:
        print(f"❌ AirSim/PX4 Error: Failed to arm/take off. Details: {e}")
        return

    # --- PHASE 3: AUTHENTICATION HANDSHAKE ---
    print("\n--- Phase 3: Authentication Handshake ---")
    try:
        # Step 1: Request Challenge from GCS
        print("📤 Sending authentication request to GCS...")
        response_1 = local_leader_node.handle_auth_request_1(UAV_SUPI)
        print(f"📥 Received challenge: RAND={response_1['rand']}")
        
        # Step 2: Calculate and Send Response
        rand = response_1['rand']
        calculated_res_star = calculate_res_star_simulated(LONG_TERM_KEY, rand)
        print(f"🔒 Calculated RES*: {calculated_res_star}")
        
        response_2 = local_leader_node.handle_auth_response_2(UAV_SUPI, calculated_res_star)
        
        if response_2.get('status') != 'AUTH_SUCCESS': 
            raise Exception("Authentication Failed - RES* mismatch")

        session_key = response_2['session_key']
        print(f"✅ Authentication SUCCESS!")
        print(f"🔑 Session Key: {session_key}")

    except Exception as e:
        print(f"❌ FATAL AUTHENTICATION ERROR: {e}")
        print("🚫 Flight aborted for security reasons.")
        return
    
    # --- PHASE 4: FLIGHT PATH EXECUTION WITH TELEMETRY LOGGING ---
    print("\n--- Phase 4: Flight Path Execution ---")
    print(f"⏱️  Flight Duration: 60 seconds")
    print(f"📊 Telemetry Log Interval: 2.0 seconds")
    
    TOTAL_FLIGHT_TIME = 60
    LOG_INTERVAL = 2.0
    PATH_SEGMENTS = [
        (10, 0, -10),    # Point A
        (10, 10, -10),   # Point B
        (0, 10, -10),    # Point C
        (0, 0, -10)      # Point D (back to start)
    ]
    
    start_time = time.time()
    path_index = 0
    telemetry_count = 0
    
    print("🛰️  Starting telemetry data collection...\n")
    
    while time.time() - start_time < TOTAL_FLIGHT_TIME:
        # Navigate to next waypoint
        wp_x, wp_y, wp_z = PATH_SEGMENTS[path_index % len(PATH_SEGMENTS)]
        path_index += 1
        
        airsim_client.moveToPositionAsync(wp_x, wp_y, wp_z, 5, timeout_sec=1).join()
        
        # Log telemetry twice per waypoint
        for i in range(2): 
            if time.time() - start_time >= TOTAL_FLIGHT_TIME: 
                break
            
            # Collect telemetry
            telemetry_data = get_telemetry_data(airsim_client)
            telemetry_count += 1
            
            # Create telemetry transaction
            telemetry_tx = {
                'type': 'TELEMETRY_TX', 
                'uav_supi': UAV_SUPI, 
                'session_key': session_key, 
                'data': telemetry_data,
                'tx_id': f'TELEM_{telemetry_count}'
            }
            
            # Add to blockchain
            result = local_leader_node.handle_telemetry_tx(telemetry_tx)
            
            if result['status'] == 'TX_BLOCK_ACK':
                print(f"📦 Block mined | TX Count: {telemetry_count} | Hash: {result['hash']}")
            
            time.sleep(LOG_INTERVAL)
    
    print(f"\n✅ Flight path completed. Total telemetry entries: {telemetry_count}")

    # --- PHASE 5: LANDING AND ARCHIVING ---
    print("\n--- Phase 5: Landing & Archiving ---")
    print("🛬 Landing UAV...")
    
    airsim_client.landAsync().join() 

    # Log final landing transaction
    final_telemetry = get_telemetry_data(airsim_client)
    final_telemetry['status'] = 'LANDING_FINAL'
    final_tx = {
        'type': 'TELEMETRY_TX', 
        'uav_supi': UAV_SUPI, 
        'session_key': session_key, 
        'data': final_telemetry,
        'tx_id': 'LANDING_FINAL'
    }
    local_leader_node.handle_telemetry_tx(final_tx)

    # Cleanup
    airsim_client.armDisarm(False)
    airsim_client.reset()
    airsim_client.enableApiControl(False)
    print("🔒 UAV disarmed and reset")
    
    # Archive the blockchain ledger
    print("\n📦 Archiving blockchain ledger...")
    archive_result = archive_current_ledger(current_flight_id)
    
    if archive_result:
        print(f"✅ Flight {current_flight_id} blockchain archived as: {archive_result}")
        print(f"📊 Total blocks in chain: {len(local_leader_node.chain)}")
        print(f"🔗 Final chain hash: {local_leader_node.chain[-1]['current_hash'][:16]}...")
    else:
        print(f"⚠️  Warning: Ledger archiving failed or file too small")
    
    print("\n" + "="*70)
    print(f"✅ UAV FLIGHT {current_flight_id} COMPLETE")
    print("="*70 + "\n")

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    try:
        run_uav_archiver()
    except KeyboardInterrupt:
        print("\n\n⚠️  Flight interrupted by user (Ctrl+C)")
        print("🚨 Emergency shutdown initiated")
    except Exception as e:
        print(f"\n\n❌ CRITICAL ERROR: {e}")
        print(f"🔍 Error Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()