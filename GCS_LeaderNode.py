"""
GCS LEADER NODE - UAV AUTHENTICATION & BLOCKCHAIN SERVER
============================================================================
Author: Muntasir Al Mamun (@Muntasir-Mamun7)
Date: 2025-11-03
Purpose: Centralized blockchain server for UAV authentication system
Version: 3.0.0 - Enterprise Role-Based Access Control System
============================================================================
"""

import json
import os
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import hashlib
import time
import threading
from datetime import datetime
import pickle
import numpy as np

# ============================================================================
# IMPORT MODULES
# ============================================================================

# Import authentication database with RBAC
try:
    from auth_db import (
        register_user, verify_user, create_session, verify_token, delete_session,
        get_user_count, get_user_role, is_admin, get_all_users, update_user_role,
        toggle_user_status, assign_uav, unassign_uav, get_user_uavs,
        get_uav_assignments, is_uav_assigned_to_user, log_activity,
        get_login_history, get_activity_log, get_system_stats as get_auth_stats
    )
    AUTH_SYSTEM_AVAILABLE = True
    print("✅ Authentication System (RBAC) loaded")
except ImportError as e:
    print(f"⚠️  Authentication system not found: {e}")
    AUTH_SYSTEM_AVAILABLE = False

# Import Smart Contracts
try:
    from smart_contracts import (
        ContractManager, 
        GeofenceContract, 
        SpeedLimitContract, 
        AltitudeSafetyContract,
        FlightDurationContract
    )
    SMART_CONTRACTS_AVAILABLE = True
    print("✅ Smart Contracts loaded")
except ImportError:
    print("⚠️  Smart Contracts module not found. Feature disabled.")
    SMART_CONTRACTS_AVAILABLE = False

# Import Anomaly Detection
try:
    from anomaly_detection import AnomalyDetector
    ANOMALY_DETECTION_AVAILABLE = True
    print("✅ Anomaly Detection loaded")
except ImportError:
    print("⚠️  Anomaly Detection module not found. Feature disabled.")
    ANOMALY_DETECTION_AVAILABLE = False

# ============================================================================
# CONFIGURATION
# ============================================================================

API_PORT = 5000     
ARCHIVE_DIR = 'flight_archives'
COUNT_FILE = 'flight_count.txt' 
ACTIVE_LEDGERS_DIR = 'active_ledgers'
MODELS_DIR = 'models'
STATIC_DIR = 'static'

# UAV Database (SUPI -> Long-term Key mapping)
UAV_DB = {
    'UAV_A1': 'K_LongTerm_A1', 
    'UAV_B2': 'K_LongTerm_B2',
    'UAV_C3': 'K_LongTerm_C3',
    'UAV_D4': 'K_LongTerm_D4'
}

# Ensure directories exist
for directory in [ARCHIVE_DIR, ACTIVE_LEDGERS_DIR, MODELS_DIR, STATIC_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# ============================================================================
# AUTHENTICATION MIDDLEWARE
# ============================================================================

def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        if not AUTH_SYSTEM_AVAILABLE:
            return jsonify({'error': 'Authentication not available'}), 503
        
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        
        username = verify_token(token)
        if not username:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        request.current_user = username
        return f(*args, **kwargs)
    
    decorated_function.__name__ = f.__name__
    return decorated_function

def require_admin(f):
    """Decorator to require admin role"""
    def decorated_function(*args, **kwargs):
        if not AUTH_SYSTEM_AVAILABLE:
            return jsonify({'error': 'Authentication not available'}), 503
        
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        
        username = verify_token(token)
        if not username:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        if not is_admin(username):
            return jsonify({'error': 'Admin access required'}), 403
        
        request.current_user = username
        return f(*args, **kwargs)
    
    decorated_function.__name__ = f.__name__
    return decorated_function

# ============================================================================
# BLOCKCHAIN & CRYPTOGRAPHIC FUNCTIONS
# ============================================================================

def hash_block(block):
    """Calculates the SHA-256 hash of a block."""
    temp_block = block.copy()
    if 'current_hash' in temp_block:
        del temp_block['current_hash'] 
    block_string = json.dumps(temp_block, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(block_string.encode()).hexdigest()

def calculate_session_key_simulated(long_term_key, rand):
    """Simulates the derivation of the Session Key (KTx)."""
    combined = (long_term_key + str(rand)).encode('utf-8')
    return hashlib.sha256(combined).hexdigest()[:16]

def generate_auth_vector_simulated(uav_supi, long_term_key):
    """Simulates the server generating the Authentication Vector (AV)."""
    rand = int(time.time() * 1000) 
    autn_data = (long_term_key + uav_supi + str(rand)).encode('utf-8')
    autn = hashlib.sha256(autn_data).hexdigest()
    xres_data = (long_term_key + str(rand) + 'Expected').encode('utf-8')
    xres_star = hashlib.sha256(xres_data).hexdigest()[:10]
    return rand, autn, xres_star, calculate_session_key_simulated(long_term_key, rand)

def calculate_res_star_simulated(long_term_key, rand):
    """Calculates the expected response (RES*)."""
    xres_data = (long_term_key + str(rand) + 'Expected').encode('utf-8')
    return hashlib.sha256(xres_data).hexdigest()[:10]

# ============================================================================
# EPOH CORE ENGINE
# ============================================================================

class EPOH_Core:
    """Enhanced Proof of History (EPOH) Core Engine."""
    
    def __init__(self, difficulty=2):
        self.difficulty = difficulty
        self.latest_hash = '0' * 64
        self.sequence_count = 0
        
    def generate_sequential_hash(self):
        """Generates the next hash in the PoH sequence."""
        data = self.latest_hash.encode('utf-8')
        new_hash = hashlib.sha256(data).hexdigest()
        self.latest_hash = new_hash
        self.sequence_count += 1
        return new_hash
        
    def embed_transaction(self, data_payload):
        """Embeds a transaction into the PoH sequence."""
        data_string = json.dumps(data_payload, sort_keys=True, separators=(',', ':'))
        combined_data = (self.latest_hash + data_string).encode('utf-8')
        self.latest_hash = hashlib.sha256(combined_data).hexdigest()
        self.sequence_count += 1
        return time.time(), self.latest_hash
        
    def create_block(self, transactions, previous_hash, current_chain_length, flight_id):
        """Creates a new blockchain block with EPOH temporal proofs."""
        self.latest_hash = previous_hash
        self.sequence_count = 0
        event_log = []
        
        for tx in transactions:
            for _ in range(self.difficulty): 
                self.generate_sequential_hash()
            tx_time, tx_hash = self.embed_transaction(tx)
            event_log.append({
                'event_type': 'TRANSACTION_EMBEDDED', 
                'timestamp': tx_time, 
                'hash_at_event': tx_hash,
                'tx_id': tx.get('tx_id'), 
                'flight_id': flight_id
            })
            
        final_block = {
            'index': current_chain_length + 1, 
            'timestamp': time.time(),
            'previous_hash': previous_hash, 
            'event_log': event_log,
            'transactions': transactions
        }
        
        final_block['current_hash'] = hash_block(final_block)
        self.latest_hash = final_block['current_hash']
        
        return final_block

# ============================================================================
# BLOCKCHAIN MANAGER
# ============================================================================

class BlockchainManager:
    """Manages multiple concurrent UAV flight blockchains."""
    
    def __init__(self):
        self.active_chains = {}  # flight_id -> chain data
        self.pending_auth = {}   # flight_id -> auth challenges
        self.epoh_cores = {}     # flight_id -> EPOH instance
        self.lock = threading.Lock()
        
    def get_next_flight_id(self):
        """Returns the next available flight ID (starting from 1)."""
        with self.lock:
            if not os.path.exists(COUNT_FILE):
                next_id = 1
            else:
                try:
                    with open(COUNT_FILE, 'r') as f:
                        next_id = int(f.read().strip()) + 1
                except:
                    next_id = 1
            
            with open(COUNT_FILE, 'w') as f:
                f.write(str(next_id))
            
            return next_id
    
    def create_genesis_block(self, flight_id, uav_supi, username=None):
        """Creates the genesis block for a new flight."""
        genesis_block = {
            'index': 0, 
            'timestamp': time.time(), 
            'previous_hash': '0',
            'event_log': [{
                'event_type': 'CHAIN_START', 
                'flight_id': flight_id,
                'uav_supi': uav_supi,
                'operator': username or 'system'
            }],
            'transactions': [{
                'tx_id': 'GENESIS_TX', 
                'data': f'Flight {flight_id} Initialized - UAV: {uav_supi}',
                'operator': username or 'system'
            }]
        }
        
        genesis_block['current_hash'] = hash_block(genesis_block)
        
        with self.lock:
            self.active_chains[flight_id] = {
                'chain': [genesis_block],
                'transaction_pool': [],
                'uav_supi': uav_supi,
                'operator': username or 'system',
                'session_key': None,
                'start_time': time.time()
            }
            
            self.epoh_cores[flight_id] = EPOH_Core(difficulty=2)
            self.epoh_cores[flight_id].latest_hash = genesis_block['current_hash']
        
        return genesis_block
    
    def save_chain(self, flight_id):
        """Saves a flight's blockchain to disk."""
        with self.lock:
            if flight_id not in self.active_chains:
                return False
                
            ledger_path = os.path.join(ACTIVE_LEDGERS_DIR, f'flight_{flight_id}.json')
            try:
                with open(ledger_path, 'w') as f:
                    json.dump(self.active_chains[flight_id]['chain'], f, indent=4)
                return True
            except Exception as e:
                print(f"Error saving chain for flight {flight_id}: {e}")
                return False
    
    def mine_block(self, flight_id):
        """Mines a new block from the transaction pool."""
        with self.lock:
            if flight_id not in self.active_chains:
                return None
                
            chain_data = self.active_chains[flight_id]
            
            if not chain_data['transaction_pool']:
                return None
            
            last_hash = chain_data['chain'][-1]['current_hash']
            
            new_block = self.epoh_cores[flight_id].create_block(
                chain_data['transaction_pool'],
                last_hash,
                len(chain_data['chain']),
                flight_id
            )
            
            chain_data['chain'].append(new_block)
            chain_data['transaction_pool'] = []
        
        self.save_chain(flight_id)
        
        return new_block['current_hash']
    
    def archive_flight(self, flight_id):
        """Archives a completed flight."""
        ledger_path = os.path.join(ACTIVE_LEDGERS_DIR, f'flight_{flight_id}.json')
        archive_path = os.path.join(ARCHIVE_DIR, f'Flight_{flight_id}.json')
        
        try:
            with self.lock:
                # Mine any remaining transactions
                if flight_id in self.active_chains and self.active_chains[flight_id]['transaction_pool']:
                    self.mine_block(flight_id)
            
            # Move to archive
            if os.path.exists(ledger_path):
                os.rename(ledger_path, archive_path)
            
            # Cleanup
            with self.lock:
                if flight_id in self.active_chains:
                    del self.active_chains[flight_id]
                if flight_id in self.epoh_cores:
                    del self.epoh_cores[flight_id]
                if flight_id in self.pending_auth:
                    del self.pending_auth[flight_id]
            
            return True
        except Exception as e:
            print(f"Error archiving flight {flight_id}: {e}")
            return False

# ============================================================================
# VERIFICATION LOGIC
# ============================================================================

def verify_log(file_path):
    """Internal verification logic for the API."""
    try:
        with open(file_path, 'r') as f:
            chain = json.load(f)
    except Exception as e:
        return {'secured': False, 'message': f'Verification Failed: Cannot load file. Error: {str(e)}', 'hash': None}

    if not chain or len(chain) < 1:
        return {'secured': False, 'message': 'Verification Failed: Chain is empty.', 'hash': None}

    for i in range(1, len(chain)):
        current_block = chain[i]
        previous_block = chain[i - 1]
        recalculatedHash = hash_block(previous_block)
        
        if current_block['previous_hash'] != recalculatedHash:
            return {'secured': False, 'message': f'🚨 TAMPERED DETECTED: Link broken at Block #{i}.', 'hash': current_block['previous_hash']}
        if current_block['timestamp'] <= previous_block['timestamp']:
            return {'secured': False, 'message': f'🚨 TAMPERED DETECTED: Chronology violation at Block #{i}.', 'hash': current_block['previous_hash']}

    return {'secured': True, 'message': '✅ SECURED: Integrity and Chronology Confirmed.', 'hash': chain[-1]['current_hash']}

# ============================================================================
# FLASK API SERVER
# ============================================================================

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # Enable CORS for frontend access
blockchain_manager = BlockchainManager()

# Initialize Smart Contracts (if available)
if SMART_CONTRACTS_AVAILABLE:
    contract_manager = ContractManager()
    contract_manager.add_contract(GeofenceContract(max_x=50, max_y=50, min_altitude=-20, max_altitude=0))
    contract_manager.add_contract(SpeedLimitContract(max_speed=8.0))
    contract_manager.add_contract(AltitudeSafetyContract(warning_threshold=-3, critical_threshold=-1))
    contract_manager.add_contract(FlightDurationContract(max_duration=120))
    print("📜 Smart Contracts System Initialized")
else:
    contract_manager = None

# Initialize Anomaly Detector (if available)
if ANOMALY_DETECTION_AVAILABLE:
    anomaly_detector = AnomalyDetector()
    
    # Train on existing historical data if available
    if os.path.exists(ARCHIVE_DIR):
        historical_flights = []
        for filename in os.listdir(ARCHIVE_DIR):
            if filename.startswith('Flight_') and filename.endswith('.json'):
                try:
                    with open(os.path.join(ARCHIVE_DIR, filename), 'r') as f:
                        flight_data = {'chain': json.load(f)}
                        historical_flights.append(flight_data)
                except:
                    pass
        
        if len(historical_flights) >= 5:
            anomaly_detector.train(historical_flights)
        else:
            print(f"⚠️  Only {len(historical_flights)} flights available. Need at least 5 for training.")
    
    print("🤖 AI Anomaly Detection System Initialized")
else:
    anomaly_detector = None

# ============================================================================
# USER AUTHENTICATION ENDPOINTS
# ============================================================================

@app.route('/api/register', methods=['POST'])
def api_register():
    """User registration endpoint"""
    if not AUTH_SYSTEM_AVAILABLE:
        return jsonify({'success': False, 'message': 'Authentication system not available'}), 503
    
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip()
    
    # Validation
    if not username or len(username) < 3:
        return jsonify({'success': False, 'message': 'Username must be at least 3 characters'}), 400
    
    if not password or len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
    
    # Register user (default role: user)
    result = register_user(username, password, email, role='user')
    
    if result['success']:
        print(f"👤 New user registered: {username}")
        log_activity('system', 'USER_REGISTERED', username, f'New user account created')
        return jsonify(result), 201
    else:
        return jsonify(result), 400

@app.route('/api/login', methods=['POST'])
def api_login():
    """User login endpoint"""
    if not AUTH_SYSTEM_AVAILABLE:
        return jsonify({'success': False, 'message': 'Authentication system not available'}), 503
    
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    # Get client info
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    if verify_user(username, password):
        token = create_session(username, ip_address, user_agent)
        role = get_user_role(username)
        
        print(f"🔐 User logged in: {username} ({role})")
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'username': username,
            'role': role
        })
    else:
        print(f"❌ Failed login attempt: {username}")
        return jsonify({
            'success': False,
            'message': 'Invalid username or password'
        }), 401

@app.route('/api/verify_token', methods=['POST'])
def api_verify_token():
    """Verify if a session token is valid"""
    if not AUTH_SYSTEM_AVAILABLE:
        return jsonify({'valid': False}), 503
    
    data = request.get_json()
    token = data.get('token')
    
    username = verify_token(token)
    
    if username:
        role = get_user_role(username)
        return jsonify({
            'valid': True,
            'username': username,
            'role': role
        })
    else:
        return jsonify({'valid': False}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Logout and invalidate session"""
    if not AUTH_SYSTEM_AVAILABLE:
        return jsonify({'success': False, 'message': 'Authentication system not available'}), 503
    
    data = request.get_json()
    token = data.get('token')
    
    if token:
        delete_session(token)
        print(f"🚪 User logged out (token: {token[:10]}...)")
    
    return jsonify({'success': True, 'message': 'Logged out successfully'})

# ============================================================================
# USER PROFILE & SETTINGS
# ============================================================================

@app.route('/api/user/profile', methods=['GET'])
@require_auth
def get_user_profile():
    """Get current user profile"""
    from auth_db import get_user_info
    
    user_info = get_user_info(request.current_user)
    
    if user_info:
        # Get assigned UAVs
        uavs = get_user_uavs(request.current_user)
        user_info['assigned_uavs'] = [uav['uav_supi'] for uav in uavs]
        
        return jsonify(user_info)
    else:
        return jsonify({'error': 'User not found'}), 404

@app.route('/api/user/my_uavs', methods=['GET'])
@require_auth
def user_get_my_uavs():
    """Get user's assigned UAVs"""
    role = get_user_role(request.current_user)
    
    if role == 'admin':
        # Admin sees all UAVs
        uavs = list(UAV_DB.keys())
        assigned_uavs = [{'uav_supi': uav, 'assigned_at': None, 'assigned_by': 'system'} for uav in uavs]
    else:
        # Normal user sees only assigned UAVs
        assigned_uavs = get_user_uavs(request.current_user)
        uavs = [uav['uav_supi'] for uav in assigned_uavs]
    
    return jsonify({
        'username': request.current_user,
        'role': role,
        'uavs': uavs,
        'assignments': assigned_uavs
    })

@app.route('/api/user/my_flights', methods=['GET'])
@require_auth
def user_get_my_flights():
    """Get user's flights (filtered by UAV assignment)"""
    role = get_user_role(request.current_user)
    
    # Get all flights
    all_flights = []
    for filename in os.listdir(ARCHIVE_DIR):
        if filename.startswith('Flight_') and filename.endswith('.json'):
            filepath = os.path.join(ARCHIVE_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    chain = json.load(f)
                    if chain and len(chain) > 0:
                        uav_supi = chain[0].get('event_log', [{}])[0].get('uav_supi', 'Unknown')
                        operator = chain[0].get('event_log', [{}])[0].get('operator', 'Unknown')
                        
                        all_flights.append({
                            'filename': filename,
                            'flight_id': filename.replace('Flight_', '').replace('.json', ''),
                            'uav_supi': uav_supi,
                            'operator': operator,
                            'blocks': len(chain),
                            'timestamp': chain[0].get('timestamp', 0)
                        })
            except:
                pass
    
    # Filter based on role
    if role == 'admin':
        # Admin sees all flights
        filtered_flights = all_flights
    else:
        # Normal user sees only their UAV flights
        user_uavs = [uav['uav_supi'] for uav in get_user_uavs(request.current_user)]
        filtered_flights = [f for f in all_flights if f['uav_supi'] in user_uavs]
    
    return jsonify({
        'username': request.current_user,
        'role': role,
        'flights': filtered_flights,
        'total': len(filtered_flights)
    })

# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@app.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_get_users():
    """Admin: Get all users"""
    users = get_all_users()
    
    # Add UAV assignments to each user
    for user in users:
        user_uavs = get_user_uavs(user['username'])
        user['assigned_uavs'] = [uav['uav_supi'] for uav in user_uavs]
    
    log_activity(request.current_user, 'VIEW_USERS', None, 'Viewed user list')
    
    return jsonify({
        'users': users,
        'total': len(users)
    })

@app.route('/api/admin/user/<string:username>/role', methods=['PUT'])
@require_admin
def admin_update_user_role(username):
    """Admin: Update user role"""
    data = request.get_json()
    new_role = data.get('role')
    
    result = update_user_role(request.current_user, username, new_role)
    
    return jsonify(result), 200 if result['success'] else 400

@app.route('/api/admin/user/<string:username>/status', methods=['PUT'])
@require_admin
def admin_toggle_user_status(username):
    """Admin: Enable/disable user account"""
    result = toggle_user_status(request.current_user, username)
    
    return jsonify(result), 200 if result['success'] else 400

@app.route('/api/admin/assign_uav', methods=['POST'])
@require_admin
def admin_assign_uav():
    """Admin: Assign UAV to user"""
    data = request.get_json()
    username = data.get('username')
    uav_supi = data.get('uav_supi')
    
    if not username or not uav_supi:
        return jsonify({'success': False, 'message': 'Missing username or uav_supi'}), 400
    
    if uav_supi not in UAV_DB:
        return jsonify({'success': False, 'message': 'Invalid UAV SUPI'}), 400
    
    result = assign_uav(request.current_user, username, uav_supi)
    
    return jsonify(result), 200 if result['success'] else 400

@app.route('/api/admin/unassign_uav', methods=['POST'])
@require_admin
def admin_unassign_uav():
    """Admin: Remove UAV assignment"""
    data = request.get_json()
    username = data.get('username')
    uav_supi = data.get('uav_supi')
    
    if not username or not uav_supi:
        return jsonify({'success': False, 'message': 'Missing username or uav_supi'}), 400
    
    result = unassign_uav(request.current_user, username, uav_supi)
    
    return jsonify(result), 200 if result['success'] else 400

@app.route('/api/admin/uav_assignments', methods=['GET'])
@require_admin
def admin_get_uav_assignments():
    """Admin: Get all UAV assignments"""
    assignments = get_uav_assignments()
    
    log_activity(request.current_user, 'VIEW_ASSIGNMENTS', None, 'Viewed UAV assignments')
    
    return jsonify({
        'assignments': assignments,
        'total': len(assignments)
    })

@app.route('/api/admin/system_stats', methods=['GET'])
@require_admin
def admin_system_stats():
    """Admin: Get comprehensive system statistics"""
    # Gather system-wide statistics
    archived_count = len([f for f in os.listdir(ARCHIVE_DIR) if f.startswith('Flight_')]) if os.path.exists(ARCHIVE_DIR) else 0
    
    with blockchain_manager.lock:
        active_count = len(blockchain_manager.active_chains)
    
    auth_stats = get_auth_stats()
    
    return jsonify({
        'total_flights': archived_count,
        'active_flights': active_count,
        'registered_uavs': len(UAV_DB),
        'auth_stats': auth_stats,
        'features': {
            'smart_contracts': SMART_CONTRACTS_AVAILABLE,
            'anomaly_detection': ANOMALY_DETECTION_AVAILABLE and anomaly_detector.trained if anomaly_detector else False
        }
    })

@app.route('/api/admin/login_history', methods=['GET'])
@require_admin
def admin_get_login_history():
    """Admin: Get login history"""
    limit = request.args.get('limit', 50, type=int)
    username = request.args.get('username', None)
    
    history = get_login_history(username, limit)
    
    log_activity(request.current_user, 'VIEW_LOGIN_HISTORY', username, f'Viewed login history')
    
    return jsonify({
        'history': history,
        'total': len(history)
    })

@app.route('/api/admin/activity_log', methods=['GET'])
@require_admin
def admin_get_activity_log():
    """Admin: Get activity log"""
    limit = request.args.get('limit', 100, type=int)
    username = request.args.get('username', None)
    
    activities = get_activity_log(username, limit)
    
    return jsonify({
        'activities': activities,
        'total': len(activities)
    })

@app.route('/api/admin/available_uavs', methods=['GET'])
@require_admin
def admin_get_available_uavs():
    """Admin: Get list of all UAVs in system"""
    uavs = []
    for uav_supi, key in UAV_DB.items():
        # Count how many users have this UAV assigned
        assignments = get_uav_assignments()
        assigned_users = [a['username'] for a in assignments if a['uav_supi'] == uav_supi and a['is_active']]
        
        uavs.append({
            'uav_supi': uav_supi,
            'long_term_key': key[:16] + '...',  # Truncate for security
            'assigned_to': assigned_users,
            'assignment_count': len(assigned_users)
        })
    
    return jsonify({
        'uavs': uavs,
        'total': len(uavs)
    })

# ============================================================================
# STATIC FILE SERVING
# ============================================================================

@app.route('/')
def index():
    """Serves the audit platform HTML."""
    return send_from_directory('static', 'audit_platform.html')

@app.route('/login.html')
def serve_login():
    """Serves the login page."""
    return send_from_directory('static', 'login.html')

@app.route('/register.html')
def serve_register():
    """Serves the registration page."""
    return send_from_directory('static', 'register.html')

@app.route('/admin.html')
def serve_admin():
    """Serves the admin panel (if exists)."""
    try:
        return send_from_directory('static', 'admin.html')
    except:
        return jsonify({'error': 'Admin panel not found'}), 404

@app.route('/styles.css')
def serve_css():
    """Serves the CSS file."""
    response = send_from_directory('static', 'styles.css')
    response.headers['Content-Type'] = 'text/css; charset=utf-8'
    return response

@app.route('/app.js')
def serve_js():
    """Serves the JavaScript file."""
    response = send_from_directory('static', 'app.js')
    response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return response

# ============================================================================
# FLIGHT DATA ENDPOINTS (With Role-Based Filtering)
# ============================================================================

@app.route('/api/list_flights', methods=['GET'])
def list_flights():
    """Endpoint to list archived flight files (filtered by user role)"""
    try:
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR)
            return jsonify([])
        
        # Get authentication token
        token = request.headers.get('Authorization')
        if token and AUTH_SYSTEM_AVAILABLE:
            username = verify_token(token)
            if username:
                role = get_user_role(username)
                user_uavs = [uav['uav_supi'] for uav in get_user_uavs(username)] if role != 'admin' else None
            else:
                # Invalid token, return public data only
                role = 'user'
                user_uavs = []
        else:
            # No auth, treat as normal user
            role = 'user'
            user_uavs = []
        
        files = os.listdir(ARCHIVE_DIR)
        flight_files = [f for f in files if f.startswith('Flight_') and f.endswith('.json')]
        
        flight_data = []
        for f in sorted(flight_files, key=lambda x: int(x.split('_')[1].split('.')[0])): 
            file_path = os.path.join(ARCHIVE_DIR, f)
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as test_file:
                        chain_data = json.load(test_file)
                        
                        if isinstance(chain_data, list) and len(chain_data) > 0:
                            uav_supi = chain_data[0].get('event_log', [{}])[0].get('uav_supi', 'Unknown')
                            
                            # Filter based on role
                            if role == 'admin' or user_uavs is None or uav_supi in user_uavs:
                                flight_data.append({
                                    'id': f, 
                                    'name': f.replace('.json', ''),
                                    'blocks': len(chain_data),
                                    'uav_supi': uav_supi
                                })
            except Exception as e:
                print(f"⚠️ Error reading {f}: {e}")
        
        return jsonify(flight_data)
        
    except Exception as e:
        print(f"❌ Error listing flights: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_log/<string:filename>', methods=['GET'])
def get_log(filename):
    """Endpoint to retrieve and verify a specific log file."""
    file_path = os.path.join(ARCHIVE_DIR, filename)
    
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({
            'verification': {'secured': False, 'message': 'Invalid filename', 'hash': None},
            'chain': []
        }), 400
    
    if not os.path.exists(file_path):
        return jsonify({
            'verification': {'secured': False, 'message': 'File not found', 'hash': None},
            'chain': []
        }), 404
    
    # Check access permissions
    token = request.headers.get('Authorization')
    if token and AUTH_SYSTEM_AVAILABLE:
        username = verify_token(token)
        if username:
            role = get_user_role(username)
            
            # Load chain to check UAV
            try:
                with open(file_path, 'r') as f:
                    chain_data = json.load(f)
                    uav_supi = chain_data[0].get('event_log', [{}])[0].get('uav_supi', 'Unknown')
                    
                    # Check if user has access
                    if role != 'admin':
                        user_uavs = [uav['uav_supi'] for uav in get_user_uavs(username)]
                        if uav_supi not in user_uavs:
                            return jsonify({'error': 'Access denied'}), 403
            except:
                pass
    
    verification_result = verify_log(file_path)
    
    try:
        with open(file_path, 'r') as f:
            chain_data = json.load(f)
    except Exception as e:
        chain_data = []
        verification_result = {'secured': False, 'message': f'Failed to load chain data: {str(e)}', 'hash': None}
    
    return jsonify({
        'verification': verification_result,
        'chain': chain_data
    })

@app.route('/api/start_flight', methods=['POST'])
def start_flight():
    """Starts a new flight blockchain"""
    data = request.json
    uav_supi = data.get('uav_supi')
    
    if not uav_supi or uav_supi not in UAV_DB:
        return jsonify({'error': 'Invalid UAV SUPI'}), 400
    
    # Get username from token if available
    token = request.headers.get('Authorization')
    username = None
    if token and AUTH_SYSTEM_AVAILABLE:
        username = verify_token(token)
        
        # Check if user has access to this UAV (unless admin)
        if username:
            role = get_user_role(username)
            if role != 'admin':
                if not is_uav_assigned_to_user(username, uav_supi):
                    return jsonify({'error': 'UAV not assigned to user'}), 403
    
    flight_id = blockchain_manager.get_next_flight_id()
    genesis_block = blockchain_manager.create_genesis_block(flight_id, uav_supi, username)
    blockchain_manager.save_chain(flight_id)
    
    print(f"✈️  Flight {flight_id} started for {uav_supi} by {username or 'system'} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if username:
        log_activity(username, 'FLIGHT_STARTED', uav_supi, f'Flight {flight_id} initiated')
    
    return jsonify({
        'status': 'success',
        'flight_id': flight_id,
        'genesis_hash': genesis_block['current_hash']
    })

@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    """Handles UAV authentication"""
    data = request.json
    flight_id = data.get('flight_id')
    uav_supi = data.get('uav_supi')
    step = data.get('step')
    
    if flight_id not in blockchain_manager.active_chains:
        return jsonify({'error': 'Invalid flight ID'}), 400
    
    if step == 1:
        long_term_key = UAV_DB[uav_supi]
        rand, autn, xres_star, ktx = generate_auth_vector_simulated(uav_supi, long_term_key)
        
        blockchain_manager.pending_auth[flight_id] = {
            'xres_star': xres_star,
            'ktx': ktx,
            'rand': rand
        }
        
        return jsonify({
            'status': 'CHALLENGE_ISSUED',
            'rand': rand,
            'autn': autn
        })
    
    elif step == 2:
        res_star_received = data.get('res_star')
        pending = blockchain_manager.pending_auth.get(flight_id)
        
        if pending and res_star_received == pending['xres_star']:
            session_key = pending['ktx']
            
            auth_tx = {
                'tx_id': f'AUTH_SUCCESS_{uav_supi}_{int(time.time())}',
                'uav_supi': uav_supi,
                'status': 'AUTHENTICATED',
                'session_key_sim': session_key,
                'auth_rand': pending['rand']
            }
            
            with blockchain_manager.lock:
                blockchain_manager.active_chains[flight_id]['transaction_pool'].append(auth_tx)
                blockchain_manager.active_chains[flight_id]['session_key'] = session_key
            
            blockchain_manager.mine_block(flight_id)
            
            print(f"🔐 Flight {flight_id} authenticated successfully")
            
            return jsonify({
                'status': 'AUTH_SUCCESS',
                'session_key': session_key
            })
        else:
            return jsonify({
                'status': 'AUTH_FAILURE',
                'reason': 'RES* mismatch'
            }), 401

@app.route('/api/log_telemetry', methods=['POST'])
def log_telemetry():
    """Logs telemetry data transaction with smart contract and anomaly detection"""
    data = request.json
    flight_id = data.get('flight_id')
    telemetry = data.get('telemetry')
    
    if flight_id not in blockchain_manager.active_chains:
        return jsonify({'error': 'Invalid flight ID'}), 400
    
    violations = []
    if contract_manager:
        telemetry['flight_id'] = flight_id
        violations = contract_manager.evaluate_all(telemetry)
    
    anomaly_result = {'anomaly': False}
    if anomaly_detector and anomaly_detector.trained:
        telemetry['timestamp'] = time.time()
        anomaly_result = anomaly_detector.detect_realtime(telemetry)
        
        if anomaly_result.get('anomaly'):
            print(f"🚨 ANOMALY DETECTED - Flight {flight_id}")
            print(f"   Severity: {anomaly_result.get('severity')}")
            print(f"   Reasons: {', '.join(anomaly_result.get('reasons', []))}")
    
    with blockchain_manager.lock:
        telemetry_tx = {
            'type': 'TELEMETRY_TX',
            'uav_supi': blockchain_manager.active_chains[flight_id]['uav_supi'],
            'session_key': blockchain_manager.active_chains[flight_id]['session_key'],
            'data': telemetry,
            'tx_id': data.get('tx_id', f'TELEM_{int(time.time())}'),
            'contract_violations': violations,
            'anomaly': anomaly_result
        }
        
        blockchain_manager.active_chains[flight_id]['transaction_pool'].append(telemetry_tx)
        pool_size = len(blockchain_manager.active_chains[flight_id]['transaction_pool'])
    
    if pool_size >= 3:
        current_hash = blockchain_manager.mine_block(flight_id)
        return jsonify({
            'status': 'TX_BLOCK_ACK',
            'hash': current_hash[:10] if current_hash else None,
            'violations': violations,
            'anomaly': anomaly_result
        })
    else:
        return jsonify({
            'status': 'TX_RECEIVED',
            'violations': violations,
            'anomaly': anomaly_result
        })

@app.route('/api/end_flight', methods=['POST'])
def end_flight():
    """Archives a completed flight"""
    data = request.json
    flight_id = data.get('flight_id')
    
    if flight_id not in blockchain_manager.active_chains:
        return jsonify({'error': 'Invalid flight ID'}), 400
    
    success = blockchain_manager.archive_flight(flight_id)
    
    if success:
        print(f"📦 Flight {flight_id} archived successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Retrain anomaly detector if needed
        if anomaly_detector and os.path.exists(ARCHIVE_DIR):
            historical_flights = []
            for filename in os.listdir(ARCHIVE_DIR):
                if filename.startswith('Flight_') and filename.endswith('.json'):
                    try:
                        with open(os.path.join(ARCHIVE_DIR, filename), 'r') as f:
                            flight_data = {'chain': json.load(f)}
                            historical_flights.append(flight_data)
                    except:
                        pass
            
            if len(historical_flights) >= 5:
                threading.Thread(target=anomaly_detector.train, args=(historical_flights,)).start()
        
        return jsonify({'status': 'success', 'message': f'Flight {flight_id} archived'})
    else:
        return jsonify({'error': 'Failed to archive flight'}), 500

@app.route('/api/active_flights', methods=['GET'])
def get_active_flights():
    """Returns currently active (in-flight) UAVs"""
    active_data = []
    
    # Get user info if authenticated
    token = request.headers.get('Authorization')
    user_uavs = None
    role = 'user'
    
    if token and AUTH_SYSTEM_AVAILABLE:
        username = verify_token(token)
        if username:
            role = get_user_role(username)
            if role != 'admin':
                user_uavs = [uav['uav_supi'] for uav in get_user_uavs(username)]
    
    with blockchain_manager.lock:
        for flight_id, chain_data in blockchain_manager.active_chains.items():
            uav_supi = chain_data.get('uav_supi', 'Unknown')
            
            # Filter based on user permissions
            if role == 'admin' or user_uavs is None or uav_supi in user_uavs:
                chain_length = len(chain_data['chain'])
                start_time = chain_data.get('start_time', time.time())
                
                active_data.append({
                    'flight_id': flight_id,
                    'uav_supi': uav_supi,
                    'operator': chain_data.get('operator', 'Unknown'),
                    'blocks': chain_length,
                    'start_time': start_time,
                    'duration': int(time.time() - start_time)
                })
    
    return jsonify({
        'active_flights': active_data,
        'count': len(active_data)
    })

@app.route('/api/flight_activity/<int:flight_id>', methods=['GET'])
def get_flight_activity(flight_id):
    """Returns recent activity for an active flight"""
    if flight_id not in blockchain_manager.active_chains:
        return jsonify({'error': 'Flight not active'}), 404
    
    with blockchain_manager.lock:
        chain = blockchain_manager.active_chains[flight_id]['chain']
        
        recent_activity = []
        for block in chain[-5:]:
            for tx in block['transactions']:
                if tx.get('type') == 'TELEMETRY_TX':
                    data = tx.get('data', {})
                    recent_activity.append({
                        'timestamp': block['timestamp'],
                        'type': 'telemetry',
                        'coordinates': f"({data.get('x_pos', 0):.2f}, {data.get('y_pos', 0):.2f})",
                        'altitude': f"{data.get('z_alt', 0):.2f}m",
                        'speed': f"{data.get('vel_mag', 0):.2f} m/s"
                    })
                elif tx.get('status') == 'AUTHENTICATED':
                    recent_activity.append({
                        'timestamp': block['timestamp'],
                        'type': 'authentication',
                        'message': 'UAV Authenticated Successfully'
                    })
    
    return jsonify({
        'flight_id': flight_id,
        'activity': recent_activity[-10:]
    })

# ============================================================================
# SMART CONTRACTS & ANOMALY DETECTION
# ============================================================================

@app.route('/api/contracts/stats', methods=['GET'])
def contract_stats():
    """Returns smart contract statistics"""
    if not contract_manager:
        return jsonify({'error': 'Smart contracts not available'}), 503
    
    return jsonify(contract_manager.get_statistics())

@app.route('/api/contracts/violations', methods=['GET'])
def contract_violations():
    """Returns all contract violations"""
    if not contract_manager:
        return jsonify({'error': 'Smart contracts not available'}), 503
    
    all_violations = []
    
    for contract in contract_manager.contracts:
        all_violations.extend(contract.violations)
    
    all_violations.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({
        'total': len(all_violations),
        'violations': all_violations[:50]
    })

@app.route('/api/anomaly/stats', methods=['GET'])
def anomaly_stats():
    """Returns anomaly detector statistics"""
    if not anomaly_detector:
        return jsonify({'error': 'Anomaly detection not available'}), 503
    
    return jsonify(anomaly_detector.get_statistics())

@app.route('/api/anomaly/retrain', methods=['POST'])
@require_admin
def retrain_anomaly_detector():
    """Retrain the anomaly detector with new data (admin only)"""
    if not anomaly_detector:
        return jsonify({'error': 'Anomaly detection not available'}), 503
    
    historical_flights = []
    
    for filename in os.listdir(ARCHIVE_DIR):
        if filename.startswith('Flight_') and filename.endswith('.json'):
            try:
                with open(os.path.join(ARCHIVE_DIR, filename), 'r') as f:
                    flight_data = {'chain': json.load(f)}
                    historical_flights.append(flight_data)
            except:
                pass
    
    if anomaly_detector.train(historical_flights):
        log_activity(request.current_user, 'AI_MODEL_RETRAINED', None, f'Retrained on {len(historical_flights)} flights')
        
        return jsonify({
            'status': 'success',
            'message': f'Model retrained on {len(historical_flights)} flights'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Not enough data to train (minimum 5 flights required)'
        }), 400

# ============================================================================
# SYSTEM STATUS & INFO
# ============================================================================

@app.route('/api/system_status', methods=['GET'])
def system_status():
    """Returns system health and statistics"""
    archived_count = len([f for f in os.listdir(ARCHIVE_DIR) if f.startswith('Flight_')]) if os.path.exists(ARCHIVE_DIR) else 0
    
    with blockchain_manager.lock:
        active_count = len(blockchain_manager.active_chains)
    
    features = {
        'smart_contracts': SMART_CONTRACTS_AVAILABLE,
        'anomaly_detection': ANOMALY_DETECTION_AVAILABLE and anomaly_detector.trained if anomaly_detector else False,
        '2d_visualization': True,
        'user_authentication': AUTH_SYSTEM_AVAILABLE,
        'role_based_access': AUTH_SYSTEM_AVAILABLE
    }
    
    user_count = get_user_count() if AUTH_SYSTEM_AVAILABLE else 0
    
    return jsonify({
        'status': 'online',
        'timestamp': time.time(),
        'active_flights': active_count,
        'archived_flights': archived_count,
        'registered_uavs': len(UAV_DB),
        'registered_users': user_count,
        'features': features,
        'version': '3.0.0',
        'author': 'Muntasir Al Mamun (@Muntasir-Mamun7)'
    })

@app.route('/api/user_stats', methods=['GET'])
def api_user_stats():
    """Get user statistics"""
    if not AUTH_SYSTEM_AVAILABLE:
        return jsonify({'total_users': 0})
    
    return jsonify({
        'total_users': get_user_count()
    })

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🌐 GCS LEADER NODE - UAV AUTHENTICATION SYSTEM v3.0.0")
    print("="*80)
    print(f"📡 API Server: http://127.0.0.1:{API_PORT}")
    print(f"📁 Archive Directory: {os.path.abspath(ARCHIVE_DIR)}")
    print(f"📂 Active Ledgers: {os.path.abspath(ACTIVE_LEDGERS_DIR)}")
    print(f"📂 Static Files: {os.path.abspath(STATIC_DIR)}")
    print(f"🔍 Audit Platform: http://127.0.0.1:{API_PORT}/")
    print(f"🔐 Login Page: http://127.0.0.1:{API_PORT}/login.html")
    print(f"📝 Register Page: http://127.0.0.1:{API_PORT}/register.html")
    print(f"🔐 Registered UAVs: {len(UAV_DB)} ({', '.join(UAV_DB.keys())})")
    
    if AUTH_SYSTEM_AVAILABLE:
        print(f"👥 Registered Users: {get_user_count()}")
        auth_stats = get_auth_stats()
        print(f"👑 Admins: {auth_stats['total_admins']}")
        print(f"📱 Active Sessions: {auth_stats['active_sessions']}")
        print(f"🔗 UAV Assignments: {auth_stats['total_assignments']}")
    
    print("-" * 80)
    print("✨ FEATURES:")
    print(f"   📜 Smart Contracts: {'✅ Enabled' if SMART_CONTRACTS_AVAILABLE else '❌ Disabled'}")
    print(f"   🤖 AI Anomaly Detection: {'✅ Enabled' if ANOMALY_DETECTION_AVAILABLE else '❌ Disabled'}")
    print(f"   📊 2D Visualization: ✅ Enabled")
    print(f"   🔐 User Authentication: {'✅ Enabled' if AUTH_SYSTEM_AVAILABLE else '❌ Disabled'}")
    print(f"   👑 Role-Based Access Control: {'✅ Enabled' if AUTH_SYSTEM_AVAILABLE else '❌ Disabled'}")
    print("-" * 80)
    print(f"👤 Author: Muntasir Al Mamun (@Muntasir-Mamun7)")
    print(f"📅 Date: 2025-11-03")
    print("="*80 + "\n")
    
    if not AUTH_SYSTEM_AVAILABLE:
        print("⚠️  WARNING: auth_db.py not found or failed to load.")
        print("⚠️  Install it for full authentication features.")
        print("=" * 80 + "\n")
    
    app.run(host='0.0.0.0', port=API_PORT, threaded=True, debug=False)