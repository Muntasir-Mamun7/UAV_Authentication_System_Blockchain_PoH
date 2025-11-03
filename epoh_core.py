import hashlib
import json
import time

# --- Configuration (Can be adapted later for election simulation) ---
UAV_IDENTIFIER = 'UAV_A1'
NODE_ID = 'Leader_Node_1'
# ------------------------------------------------------------------

class EPOH_Core:
    """
    Implements the simplified Proof-of-History (PoH) function.
    It generates a sequential hash sequence, embedding transaction data
    at specific points to create a verifiable, chronological timeline.
    """
    def __init__(self, difficulty=5):
        # Difficulty represents the number of sequential hash iterations between blocks
        self.difficulty = difficulty 
        self.latest_hash = '0' * 64 # Initial hash sequence seed
        self.sequence_count = 0

    def generate_sequential_hash(self):
        """Generates the next hash in the sequence."""
        data = self.latest_hash.encode('utf-8')
        new_hash = hashlib.sha256(data).hexdigest()
        self.latest_hash = new_hash
        self.sequence_count += 1
        return new_hash

    def embed_transaction(self, data_payload):
        """
        Incorporates transaction data into the sequential hash to timestamp it.
        This simulates the PoH Generator receiving a transaction and embedding it.
        """
        # Ensure the data is deterministic for consistent hashing
        data_string = json.dumps(data_payload, sort_keys=True)
        combined_data = (self.latest_hash + data_string).encode('utf-8')
        
        # Hash the combined data
        self.latest_hash = hashlib.sha256(combined_data).hexdigest()
        self.sequence_count += 1
        
        # Return the time and hash at which the event was recorded
        return time.time(), self.latest_hash

    def create_block(self, transactions, previous_hash):
        """
        Leader Node function: creates a new block containing a PoH-proof.
        In this light-weight version, the PoH-proof is the final hash
        after a series of sequential operations.
        """
        # 1. Start the sequential hashing sequence
        self.latest_hash = previous_hash
        self.sequence_count = 0
        
        event_log = []
        
        for tx in transactions:
            # Generate intermediate hashes (simulating time delay)
            for _ in range(self.difficulty):
                self.generate_sequential_hash()
            
            # 2. Embed the transaction data (The EPOH step)
            tx_time, tx_hash = self.embed_transaction(tx)
            
            event_log.append({
                'event_type': 'TRANSACTION_EMBEDDED',
                'timestamp': tx_time,
                'hash_at_event': tx_hash,
                'tx_id': tx.get('tx_id')
            })

        # 3. Finalize the Block
        final_block = {
            'index': len(self.chain) + 1 if hasattr(self, 'chain') else 1,
            'timestamp': time.time(),
            'previous_hash': previous_hash,
            'event_log': event_log, # The verifiable PoH timeline
            'transactions': transactions
        }
        
        # The block hash is based on the final PoH-linked state (latest_hash)
        final_block['current_hash'] = self.latest_hash 
        return final_block

# --- Simplified ECC Simulation for Authentication (ECC) ---

# Note: In a real system, you'd use a library like 'cryptography' 
# to generate curve keys and perform ECDH/ECDSA. 
# Here, we simulate the *result* of the ECC protocol for speed.

def generate_key_pair_simulated():
    """Simulates ECC key pair generation."""
    # Private key (K_priv) and Public key (PKNode)
    return "NodePrivKey_Sim", "NodePubKey_Sim"

def calculate_session_key_simulated(long_term_key, rand):
    """Simulates the derivation of the Session Key (KTx)."""
    # KTx = HASH(K | RAND)
    combined = (long_term_key + str(rand)).encode('utf-8')
    return hashlib.sha256(combined).hexdigest()[:16] # 16-char session key

def generate_auth_vector_simulated(uav_supi, long_term_key):
    """
    Simulates the server generating the Authentication Vector (AV).
    AV = (RAND, AUTN, XRES*)
    """
    rand = int(time.time() * 1000) # Unique Random Challenge
    # AUTN = HASH(K | SUPI | RAND) -> Authentication Token
    autn_data = (long_term_key + uav_supi + str(rand)).encode('utf-8')
    autn = hashlib.sha256(autn_data).hexdigest()
    
    # XRES* (Expected Response) -> Used for final verification
    xres_data = (long_term_key + str(rand) + 'Expected').encode('utf-8')
    xres_star = hashlib.sha256(xres_data).hexdigest()[:10]
    
    return rand, autn, xres_star, calculate_session_key_simulated(long_term_key, rand)