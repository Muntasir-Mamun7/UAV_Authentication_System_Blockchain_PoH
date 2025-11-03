"""
User Authentication & Authorization Database with Role-Based Access Control (RBAC)
Author: Muntasir Al Mamun (@Muntasir-Mamun7)
Date: 2025-11-03
Version: 2.0.0 - Enterprise Role System with UAV Assignment
"""

import sqlite3
import hashlib
import secrets
from datetime import datetime
import os

DB_FILE = 'uav_users.db'

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_db():
    """Initialize the database with users, sessions, and UAV assignment tables"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Users table with role support
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Sessions table for token-based authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        )
    ''')
    
    # UAV assignments table (many-to-many relationship)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uav_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            uav_supi TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assigned_by TEXT,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
            UNIQUE(username, uav_supi)
        )
    ''')
    
    # Login history for security auditing
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            success BOOLEAN,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        )
    ''')
    
    # Activity log for admin auditing
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    
    # Create default admin user if no users exist
    cursor.execute('SELECT COUNT(*) FROM users')
    user_count = cursor.fetchone()[0]
    
    if user_count == 0:
        print("📝 Creating default admin account...")
        admin_password = 'admin123'  # Change this in production!
        password_hash = hash_password(admin_password)
        
        cursor.execute(
            'INSERT INTO users (username, password_hash, email, role, is_active) VALUES (?, ?, ?, ?, ?)',
            ('admin', password_hash, 'admin@uav-system.local', 'admin', 1)
        )
        conn.commit()
        
        print("✅ Default admin account created:")
        print("   Username: admin")
        print("   Password: admin123")
        print("   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
    
    conn.close()
    print("✅ Database initialized with RBAC system")

# ============================================================================
# PASSWORD HASHING
# ============================================================================

def hash_password(password):
    """Hash a password using SHA-256 with salt"""
    salt = "UAV_AUTH_SYSTEM_SALT_2025"  # In production, use per-user salt
    return hashlib.sha256((password + salt).encode()).hexdigest()

# ============================================================================
# USER MANAGEMENT
# ============================================================================

def register_user(username, password, email=None, role='user'):
    """Register a new user"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Validate username
        if len(username) < 3:
            return {'success': False, 'message': 'Username must be at least 3 characters'}
        
        # Validate password
        if len(password) < 6:
            return {'success': False, 'message': 'Password must be at least 6 characters'}
        
        password_hash = hash_password(password)
        
        cursor.execute(
            'INSERT INTO users (username, password_hash, email, role, is_active) VALUES (?, ?, ?, ?, ?)',
            (username, password_hash, email, role, 1)
        )
        
        conn.commit()
        conn.close()
        
        # Log activity
        log_activity('system', 'USER_REGISTERED', username, f'New user registered with role: {role}')
        
        return {'success': True, 'message': 'Registration successful'}
    
    except sqlite3.IntegrityError:
        return {'success': False, 'message': 'Username already exists'}
    except Exception as e:
        return {'success': False, 'message': f'Registration failed: {str(e)}'}

def verify_user(username, password):
    """Verify username and password"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    password_hash = hash_password(password)
    
    cursor.execute(
        'SELECT username, is_active FROM users WHERE username = ? AND password_hash = ?',
        (username, password_hash)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        # Check if user is active
        if not result[1]:
            return False
        
        # Update last login time
        update_last_login(username)
        return True
    
    return False

def update_last_login(username):
    """Update user's last login timestamp"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        'UPDATE users SET last_login = ? WHERE username = ?',
        (datetime.now(), username)
    )
    
    conn.commit()
    conn.close()

def get_user_info(username):
    """Get detailed user information"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT username, email, role, is_active, created_at, last_login FROM users WHERE username = ?',
        (username,)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'username': result[0],
            'email': result[1],
            'role': result[2],
            'is_active': bool(result[3]),
            'created_at': result[4],
            'last_login': result[5]
        }
    return None

def get_user_role(username):
    """Get user's role"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT role FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else 'user'

def is_admin(username):
    """Check if user is admin"""
    return get_user_role(username) == 'admin'

def get_all_users():
    """Get all users (admin only)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT username, email, role, is_active, created_at, last_login FROM users ORDER BY created_at DESC'
    )
    
    users = []
    for row in cursor.fetchall():
        users.append({
            'username': row[0],
            'email': row[1],
            'role': row[2],
            'is_active': bool(row[3]),
            'created_at': row[4],
            'last_login': row[5]
        })
    
    conn.close()
    return users

def update_user_role(admin_username, target_username, new_role):
    """Update user role (admin only)"""
    if not is_admin(admin_username):
        return {'success': False, 'message': 'Unauthorized: Admin access required'}
    
    if new_role not in ['user', 'admin']:
        return {'success': False, 'message': 'Invalid role. Must be "user" or "admin"'}
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE users SET role = ? WHERE username = ?',
            (new_role, target_username)
        )
        
        conn.commit()
        conn.close()
        
        log_activity(admin_username, 'ROLE_CHANGED', target_username, f'Role changed to: {new_role}')
        
        return {'success': True, 'message': f'User {target_username} role updated to {new_role}'}
    
    except Exception as e:
        return {'success': False, 'message': f'Failed to update role: {str(e)}'}

def toggle_user_status(admin_username, target_username):
    """Enable/disable user account (admin only)"""
    if not is_admin(admin_username):
        return {'success': False, 'message': 'Unauthorized: Admin access required'}
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute('SELECT is_active FROM users WHERE username = ?', (target_username,))
        result = cursor.fetchone()
        
        if not result:
            return {'success': False, 'message': 'User not found'}
        
        new_status = not bool(result[0])
        
        cursor.execute(
            'UPDATE users SET is_active = ? WHERE username = ?',
            (new_status, target_username)
        )
        
        conn.commit()
        conn.close()
        
        status_text = 'enabled' if new_status else 'disabled'
        log_activity(admin_username, 'USER_STATUS_CHANGED', target_username, f'Account {status_text}')
        
        return {'success': True, 'message': f'User {target_username} {status_text}'}
    
    except Exception as e:
        return {'success': False, 'message': f'Failed to update status: {str(e)}'}

def get_user_count():
    """Get total number of registered users"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
    count = cursor.fetchone()[0]
    
    conn.close()
    return count

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def create_session(username, ip_address=None, user_agent=None):
    """Create a new session token for a user"""
    token = secrets.token_urlsafe(32)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Set expiration time (24 hours from now)
    from datetime import timedelta
    expires_at = datetime.now() + timedelta(hours=24)
    
    cursor.execute(
        'INSERT INTO sessions (token, username, expires_at, ip_address, user_agent) VALUES (?, ?, ?, ?, ?)',
        (token, username, expires_at, ip_address, user_agent)
    )
    
    conn.commit()
    conn.close()
    
    # Log login
    log_login(username, ip_address, user_agent, success=True)
    
    return token

def verify_token(token):
    """Check if a token is valid and return username"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT username, expires_at FROM sessions WHERE token = ?',
        (token,)
    )
    result = cursor.fetchone()
    
    conn.close()
    
    if result:
        username, expires_at = result
        
        # Check if token expired
        if expires_at:
            expiry_time = datetime.fromisoformat(expires_at)
            if datetime.now() > expiry_time:
                delete_session(token)
                return None
        
        return username
    
    return None

def delete_session(token):
    """Delete a session (logout)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get username before deleting
    cursor.execute('SELECT username FROM sessions WHERE token = ?', (token,))
    result = cursor.fetchone()
    
    cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
    
    conn.commit()
    conn.close()
    
    if result:
        log_activity(result[0], 'LOGOUT', None, 'User logged out')

def delete_all_user_sessions(username):
    """Delete all sessions for a user (force logout)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM sessions WHERE username = ?', (username,))
    
    conn.commit()
    conn.close()

def clean_expired_sessions():
    """Remove expired sessions from database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        'DELETE FROM sessions WHERE expires_at < ?',
        (datetime.now(),)
    )
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted_count

# ============================================================================
# UAV ASSIGNMENT MANAGEMENT
# ============================================================================

def assign_uav(admin_username, username, uav_supi):
    """Assign a UAV to a user (admin only)"""
    if not is_admin(admin_username):
        return {'success': False, 'message': 'Unauthorized: Admin access required'}
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if assignment already exists
        cursor.execute(
            'SELECT id FROM uav_assignments WHERE username = ? AND uav_supi = ?',
            (username, uav_supi)
        )
        
        if cursor.fetchone():
            conn.close()
            return {'success': False, 'message': f'UAV {uav_supi} already assigned to {username}'}
        
        cursor.execute(
            'INSERT INTO uav_assignments (username, uav_supi, assigned_by, is_active) VALUES (?, ?, ?, ?)',
            (username, uav_supi, admin_username, 1)
        )
        
        conn.commit()
        conn.close()
        
        log_activity(admin_username, 'UAV_ASSIGNED', username, f'Assigned UAV {uav_supi}')
        
        return {'success': True, 'message': f'UAV {uav_supi} assigned to {username}'}
    
    except Exception as e:
        return {'success': False, 'message': f'Failed to assign UAV: {str(e)}'}

def unassign_uav(admin_username, username, uav_supi):
    """Remove UAV assignment from user (admin only)"""
    if not is_admin(admin_username):
        return {'success': False, 'message': 'Unauthorized: Admin access required'}
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute(
            'DELETE FROM uav_assignments WHERE username = ? AND uav_supi = ?',
            (username, uav_supi)
        )
        
        if cursor.rowcount == 0:
            conn.close()
            return {'success': False, 'message': 'Assignment not found'}
        
        conn.commit()
        conn.close()
        
        log_activity(admin_username, 'UAV_UNASSIGNED', username, f'Unassigned UAV {uav_supi}')
        
        return {'success': True, 'message': f'UAV {uav_supi} unassigned from {username}'}
    
    except Exception as e:
        return {'success': False, 'message': f'Failed to unassign UAV: {str(e)}'}

def get_user_uavs(username):
    """Get all UAVs assigned to a user"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT uav_supi, assigned_at, assigned_by FROM uav_assignments WHERE username = ? AND is_active = 1',
        (username,)
    )
    
    uavs = []
    for row in cursor.fetchall():
        uavs.append({
            'uav_supi': row[0],
            'assigned_at': row[1],
            'assigned_by': row[2]
        })
    
    conn.close()
    return uavs

def get_uav_assignments():
    """Get all UAV assignments (admin only)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT username, uav_supi, assigned_at, assigned_by, is_active FROM uav_assignments ORDER BY assigned_at DESC'
    )
    
    assignments = []
    for row in cursor.fetchall():
        assignments.append({
            'username': row[0],
            'uav_supi': row[1],
            'assigned_at': row[2],
            'assigned_by': row[3],
            'is_active': bool(row[4])
        })
    
    conn.close()
    return assignments

def is_uav_assigned_to_user(username, uav_supi):
    """Check if a specific UAV is assigned to a user"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT id FROM uav_assignments WHERE username = ? AND uav_supi = ? AND is_active = 1',
        (username, uav_supi)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    return result is not None

# ============================================================================
# LOGGING & AUDITING
# ============================================================================

def log_login(username, ip_address=None, user_agent=None, success=True):
    """Log login attempt"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO login_history (username, ip_address, user_agent, success) VALUES (?, ?, ?, ?)',
        (username, ip_address, user_agent, success)
    )
    
    conn.commit()
    conn.close()

def log_activity(username, action, target=None, details=None):
    """Log user activity"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO activity_log (username, action, target, details) VALUES (?, ?, ?, ?)',
        (username, action, target, details)
    )
    
    conn.commit()
    conn.close()

def get_login_history(username=None, limit=50):
    """Get login history"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if username:
        cursor.execute(
            'SELECT username, login_time, ip_address, user_agent, success FROM login_history WHERE username = ? ORDER BY login_time DESC LIMIT ?',
            (username, limit)
        )
    else:
        cursor.execute(
            'SELECT username, login_time, ip_address, user_agent, success FROM login_history ORDER BY login_time DESC LIMIT ?',
            (limit,)
        )
    
    history = []
    for row in cursor.fetchall():
        history.append({
            'username': row[0],
            'login_time': row[1],
            'ip_address': row[2],
            'user_agent': row[3],
            'success': bool(row[4])
        })
    
    conn.close()
    return history

def get_activity_log(username=None, limit=100):
    """Get activity log"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if username:
        cursor.execute(
            'SELECT username, action, target, details, timestamp FROM activity_log WHERE username = ? ORDER BY timestamp DESC LIMIT ?',
            (username, limit)
        )
    else:
        cursor.execute(
            'SELECT username, action, target, details, timestamp FROM activity_log ORDER BY timestamp DESC LIMIT ?',
            (limit,)
        )
    
    activities = []
    for row in cursor.fetchall():
        activities.append({
            'username': row[0],
            'action': row[1],
            'target': row[2],
            'details': row[3],
            'timestamp': row[4]
        })
    
    conn.close()
    return activities

# ============================================================================
# SYSTEM STATISTICS
# ============================================================================

def get_system_stats():
    """Get comprehensive system statistics"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Total users
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
    total_users = cursor.fetchone()[0]
    
    # Total admins
    cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin" AND is_active = 1')
    total_admins = cursor.fetchone()[0]
    
    # Active sessions
    cursor.execute('SELECT COUNT(*) FROM sessions WHERE expires_at > ?', (datetime.now(),))
    active_sessions = cursor.fetchone()[0]
    
    # Total UAV assignments
    cursor.execute('SELECT COUNT(*) FROM uav_assignments WHERE is_active = 1')
    total_assignments = cursor.fetchone()[0]
    
    # Recent logins (last 24 hours)
    from datetime import timedelta
    yesterday = datetime.now() - timedelta(hours=24)
    cursor.execute('SELECT COUNT(*) FROM login_history WHERE login_time > ? AND success = 1', (yesterday,))
    recent_logins = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_admins': total_admins,
        'active_sessions': active_sessions,
        'total_assignments': total_assignments,
        'recent_logins': recent_logins
    }

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def backup_database(backup_path='backups'):
    """Create a backup of the database"""
    if not os.path.exists(backup_path):
        os.makedirs(backup_path)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_path, f'uav_users_{timestamp}.db')
    
    import shutil
    shutil.copy2(DB_FILE, backup_file)
    
    return backup_file

def reset_database():
    """Reset database (DANGEROUS - USE WITH CAUTION)"""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    init_db()

# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize database on import
if __name__ == '__main__':
    print("="*70)
    print("UAV Authentication Database Management System")
    print("Author: Muntasir Al Mamun")
    print("="*70)
    init_db()
    
    # Display statistics
    stats = get_system_stats()
    print(f"\n📊 System Statistics:")
    print(f"   Total Users: {stats['total_users']}")
    print(f"   Admins: {stats['total_admins']}")
    print(f"   Active Sessions: {stats['active_sessions']}")
    print(f"   UAV Assignments: {stats['total_assignments']}")
    print(f"   Recent Logins (24h): {stats['recent_logins']}")
    print("\n✅ Database ready for use")
else:
    init_db()