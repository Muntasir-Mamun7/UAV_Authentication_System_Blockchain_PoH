"""
UAV Client 2 - Square Pattern Flight (Testing Version)
Author: Muntasir Al Mamun (@Muntasir-Mamun7)
Date: 2025-11-03
Version: 3.0.0 - Optimized for testing with full diagnostics
Works with GCS_LeaderNode.py REST API (port 5000)
"""

import airsim
import requests
import time
import hashlib
import math
import sys

# =============================================================================
# CONFIGURATION
# =============================================================================

# UAV Configuration
UAV_ID = 'UAV_2'
UAV_SUPI = 'UAV_B2'
LONG_TERM_KEY = 'K_LongTerm_B2'
FLIGHT_DURATION = 30  # Reduced to 30 seconds for quick testing

# API Configuration
GCS_API_BASE = 'http://127.0.0.1:5000/api'

# AirSim Configuration
AIRSIM_HOST_IP = "192.168.43.231"  # Your AirSim IP

# Flight Pattern Configuration
TAKEOFF_ALTITUDE = 10.0  # meters
FLIGHT_VELOCITY = 5.0    # m/s
LOG_INTERVAL = 2.0       # seconds between telemetry logs


# =============================================================================
# UAV CLIENT CLASS
# =============================================================================

class UAVClient:
    """UAV Client with AirSim and REST API integration."""
    
    def __init__(self):
        """Initialize UAV Client."""
        self.uav_id = UAV_ID
        self.uav_supi = UAV_SUPI
        self.long_term_key = LONG_TERM_KEY
        self.flight_duration = FLIGHT_DURATION
        
        self.flight_id = None
        self.session_key = None
        self.authenticated = False
        self.start_time = None
        
        # Initialize AirSim connection
        self.airsim_client = None
        self.connect_airsim()
    
    # =========================================================================
    # AIRSIM CONNECTION
    # =========================================================================
    
    def connect_airsim(self):
        """Connect to AirSim."""
        try:
            print(f"🔌 Connecting to AirSim at {AIRSIM_HOST_IP}...")
            self.airsim_client = airsim.MultirotorClient(ip=AIRSIM_HOST_IP)
            self.airsim_client.confirmConnection()
            print("✅ AirSim API Connection Confirmed")
            
            # Wait for PX4 link
            print("⏳ Awaiting full PX4 link (3s delay)...")
            time.sleep(3)
            
            # Enable API control
            self.airsim_client.enableApiControl(True)
            self.airsim_client.armDisarm(True)
            print("✅ UAV Armed and Ready")
            
        except Exception as e:
            print(f"❌ Failed to connect to AirSim: {e}")
            print("⚠️  Make sure AirSim/Unreal Engine is running!")
            raise
    
    # =========================================================================
    # GCS COMMUNICATION
    # =========================================================================
    
    def start_flight(self):
        """Start a new flight."""
        try:
            print(f"\n{'='*70}")
            print(f"📡 Connecting to GCS at {GCS_API_BASE}...")
            print(f"{'='*70}")
            
            response = requests.post(
                f"{GCS_API_BASE}/start_flight", 
                json={'uav_supi': self.uav_supi},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.flight_id = data['flight_id']
                self.start_time = time.time()
                
                print(f"✅ Connected to GCS Leader Node")
                print(f"✈️  Flight {self.flight_id} started")
                print(f"🔗 Genesis Hash: {data['genesis_hash'][:16]}...")
                return True
            else:
                print(f"❌ Failed to start flight")
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to GCS at {GCS_API_BASE}")
            print("⚠️  Make sure GCS_LeaderNode.py is running!")
            return False
        except requests.exceptions.Timeout:
            print(f"❌ Connection to GCS timed out")
            return False
        except Exception as e:
            print(f"❌ GCS Connection Error: {e}")
            return False
    
    def authenticate(self):
        """Perform 5G-AKA authentication."""
        try:
            print(f"\n{'='*70}")
            print(f"🔐 Starting Authentication...")
            print(f"{'='*70}")
            
            # Step 1: Request challenge
            response = requests.post(
                f"{GCS_API_BASE}/authenticate", 
                json={
                    'flight_id': self.flight_id,
                    'uav_supi': self.uav_supi,
                    'step': 1
                },
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"❌ Authentication challenge failed")
                return False
            
            challenge = response.json()
            rand = challenge['rand']
            
            print(f"📥 Received challenge (RAND: {str(rand)[:16]}...)")
            
            # Step 2: Calculate response (RES*)
            xres_data = (self.long_term_key + str(rand) + 'Expected').encode('utf-8')
            res_star = hashlib.sha256(xres_data).hexdigest()[:10]
            
            print(f"🔢 Calculated RES*: {res_star}...")
            
            # Step 3: Send response
            response = requests.post(
                f"{GCS_API_BASE}/authenticate", 
                json={
                    'flight_id': self.flight_id,
                    'uav_supi': self.uav_supi,
                    'step': 2,
                    'res_star': res_star
                },
                timeout=10
            )
            
            if response.status_code == 200:
                auth_result = response.json()
                if auth_result['status'] == 'AUTH_SUCCESS':
                    self.session_key = auth_result['session_key']
                    self.authenticated = True
                    print(f"✅ Mutual Authentication SUCCESS")
                    print(f"🔑 Session Key: {self.session_key[:16]}...")
                    return True
            
            print(f"❌ Authentication failed")
            print(f"Response: {response.text}")
            return False
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
    
    # =========================================================================
    # TELEMETRY
    # =========================================================================
    
    def get_telemetry(self):
        """Get current telemetry from AirSim."""
        state = self.airsim_client.getMultirotorState()
        pos = state.kinematics_estimated.position
        vel = state.kinematics_estimated.linear_velocity
        
        return {
            'x_pos': round(pos.x_val, 3),
            'y_pos': round(pos.y_val, 3),
            'z_alt': round(pos.z_val, 3),
            'vel_mag': round((vel.x_val**2 + vel.y_val**2 + vel.z_val**2)**0.5, 3),
            'timestamp': time.time()
        }
    
    def log_telemetry(self, show_details=False):
        """Log telemetry to blockchain."""
        if not self.authenticated:
            return False
        
        try:
            telemetry = self.get_telemetry()
            
            response = requests.post(
                f"{GCS_API_BASE}/log_telemetry", 
                json={
                    'flight_id': self.flight_id,
                    'telemetry': telemetry,
                    'tx_id': f'TELEM_{self.uav_id}_{int(time.time() * 1000)}'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Show block confirmations
                if result['status'] == 'TX_BLOCK_ACK':
                    print(f"📦 Block mined | Hash: {result['hash'][:10]}...")
                elif show_details:
                    print(f"📤 TX sent | Pos: ({telemetry['x_pos']:.1f}, {telemetry['y_pos']:.1f}, {telemetry['z_alt']:.1f})")
                
                # Show violations (important only)
                if result.get('violations'):
                    for violation in result['violations']:
                        if violation.get('severity') in ['WARNING', 'CRITICAL']:
                            print(f"⚠️  {violation['contract']}: {violation['message']}")
                
                # Show critical anomalies only
                if result.get('anomaly', {}).get('anomaly'):
                    anomaly = result['anomaly']
                    if anomaly.get('severity') == 'CRITICAL':
                        print(f"🚨 CRITICAL ANOMALY DETECTED")
                
                return True
            else:
                if show_details:
                    print(f"⚠️  Telemetry failed: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            if show_details:
                print(f"⚠️  Telemetry timeout (continuing...)")
            return False
        except Exception as e:
            if show_details:
                print(f"⚠️  Telemetry error: {e}")
            return False
    
    # =========================================================================
    # FLIGHT OPERATIONS
    # =========================================================================
    
    def takeoff(self):
        """Takeoff to specified altitude."""
        print(f"\n{'='*70}")
        print(f"🛫 TAKEOFF SEQUENCE")
        print(f"{'='*70}")
        print(f"Target altitude: {TAKEOFF_ALTITUDE}m")
        
        self.airsim_client.takeoffAsync(timeout_sec=10).join()
        print("✅ Takeoff initiated")
        
        self.airsim_client.moveToZAsync(-TAKEOFF_ALTITUDE, velocity=2).join()
        print(f"✅ Reached {TAKEOFF_ALTITUDE}m altitude")
        
        time.sleep(1)
    
    def fly_square_pattern(self):
        """Fly square pattern with telemetry logging."""
        print(f"\n{'='*70}")
        print(f"🛫 SQUARE FLIGHT PATTERN")
        print(f"{'='*70}")
        print(f"Pattern: 10m x 10m square")
        print(f"Velocity: {FLIGHT_VELOCITY} m/s")
        print(f"Duration: {self.flight_duration}s")
        print(f"{'='*70}\n")
        
        # Define path (smaller square for testing)
        PATH_SEGMENTS = [
            (10, 0, -TAKEOFF_ALTITUDE, "East"),
            (10, 10, -TAKEOFF_ALTITUDE, "Northeast"),
            (0, 10, -TAKEOFF_ALTITUDE, "North"),
            (0, 0, -TAKEOFF_ALTITUDE, "Origin")
        ]
        
        for i, (wp_x, wp_y, wp_z, description) in enumerate(PATH_SEGMENTS, 1):
            print(f"📍 Waypoint {i}/4: {description} ({wp_x}, {wp_y})")
            
            # Move to waypoint
            self.airsim_client.moveToPositionAsync(
                wp_x, wp_y, wp_z, 
                FLIGHT_VELOCITY, 
                timeout_sec=15
            ).join()
            
            print(f"✅ Arrived at {description}")
            
            # Log telemetry twice at each waypoint
            for j in range(2):
                self.log_telemetry(show_details=True)
                time.sleep(LOG_INTERVAL)
            
            # Show remaining time
            elapsed = time.time() - self.start_time
            remaining = max(0, self.flight_duration - elapsed)
            if remaining > 0:
                print(f"⏳ {int(remaining)}s remaining in flight...\n")
    
    def hover_and_log(self):
        """Hover and continue logging for remaining duration."""
        elapsed = time.time() - self.start_time
        remaining = max(0, self.flight_duration - elapsed)
        
        if remaining > 5:
            print(f"\n{'='*70}")
            print(f"⏳ HOVERING AND LOGGING")
            print(f"{'='*70}")
            print(f"Remaining time: {int(remaining)}s\n")
            
            logs_remaining = int(remaining / LOG_INTERVAL)
            
            for i in range(logs_remaining):
                self.log_telemetry(show_details=(i % 5 == 0))  # Show details every 5th log
                
                elapsed = time.time() - self.start_time
                remaining = self.flight_duration - elapsed
                
                if remaining <= 0:
                    break
                
                # Show countdown every 10 seconds
                if int(remaining) % 10 == 0:
                    print(f"⏳ {int(remaining)}s remaining...")
                
                time.sleep(LOG_INTERVAL)
    
    def land(self):
        """Land the drone."""
        print(f"\n{'='*70}")
        print(f"🛬 LANDING SEQUENCE")
        print(f"{'='*70}")
        
        # Get current position for logging
        pos = self.get_telemetry()
        print(f"Landing position: ({pos['x_pos']:.2f}, {pos['y_pos']:.2f}, {abs(pos['z_alt']):.2f}m)")
        
        # Log final telemetry with landing status
        try:
            telemetry = self.get_telemetry()
            telemetry['status'] = 'LANDING_FINAL'
            
            requests.post(
                f"{GCS_API_BASE}/log_telemetry", 
                json={
                    'flight_id': self.flight_id,
                    'telemetry': telemetry,
                    'tx_id': f'LAND_{self.uav_id}_{int(time.time())}'
                },
                timeout=10
            )
            print("📤 Final telemetry logged")
        except:
            pass
        
        # Execute landing
        print("🛬 Initiating landing...")
        landing_task = self.airsim_client.landAsync()
        landing_task.join()
        
        print("⏳ Waiting for touchdown (4s)...")
        time.sleep(4)
        
        # Disarm
        self.airsim_client.armDisarm(False)
        self.airsim_client.enableApiControl(False)
        
        print("✅ Landed and disarmed")
    
    def end_flight(self):
        """End flight and archive to blockchain."""
        if not self.flight_id:
            print("⚠️  No flight_id to archive")
            return False
        
        print(f"\n{'='*70}")
        print(f"📦 ARCHIVING FLIGHT TO BLOCKCHAIN")
        print(f"{'='*70}")
        print(f"Flight ID: {self.flight_id}")
        print(f"Archiving to: {GCS_API_BASE}/end_flight")
        
        try:
            print("⏳ Sending archive request (timeout: 30s)...")
            
            response = requests.post(
                f"{GCS_API_BASE}/end_flight", 
                json={'flight_id': self.flight_id},
                timeout=30  # Increased timeout for AI retraining
            )
            
            print(f"📡 Response received:")
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"   Message: {result.get('message', 'Success')}")
                print(f"✅ Flight {self.flight_id} archived successfully!")
                print(f"📁 File: flight_archives/Flight_{self.flight_id}.json")
                return True
            else:
                print(f"❌ Archive failed")
                print(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"⚠️  Archive request timed out after 30s")
            print(f"⚠️  Flight may still be archiving in background...")
            print(f"⚠️  Check GCS terminal for confirmation")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Connection error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error ending flight: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # =========================================================================
    # MAIN FLIGHT EXECUTION
    # =========================================================================
    
    def run(self):
        """Main flight execution."""
        print(f"\n{'='*70}")
        print(f"🚁 UAV CLIENT 2 - TESTING MODE")
        print(f"{'='*70}")
        print(f"UAV ID: {self.uav_id}")
        print(f"SUPI: {self.uav_supi}")
        print(f"Flight Duration: {self.flight_duration}s")
        print(f"AirSim: {AIRSIM_HOST_IP}")
        print(f"GCS API: {GCS_API_BASE}")
        print(f"{'='*70}\n")
        
        # Step 1: Start flight
        if not self.start_flight():
            print("\n❌ Failed to start flight. Aborting.")
            return False
        
        time.sleep(1)
        
        # Step 2: Authenticate
        if not self.authenticate():
            print("\n❌ Authentication failed. Aborting.")
            self.emergency_land()
            return False
        
        time.sleep(1)
        
        # Step 3: Execute flight
        try:
            # Takeoff
            self.takeoff()
            
            # Fly pattern
            self.fly_square_pattern()
            
            # Hover and log for remaining time
            self.hover_and_log()
            
            # Land
            self.land()
            
            # Archive flight
            self.end_flight()
            
            # Final summary
            elapsed = time.time() - self.start_time
            print(f"\n{'='*70}")
            print(f"✅ FLIGHT COMPLETED SUCCESSFULLY")
            print(f"{'='*70}")
            print(f"Flight ID: {self.flight_id}")
            print(f"Duration: {elapsed:.1f}s")
            print(f"Status: ARCHIVED")
            print(f"{'='*70}\n")
            
            return True
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Flight interrupted by user!")
            self.emergency_land()
            return False
            
        except Exception as e:
            print(f"\n❌ Flight error: {e}")
            import traceback
            traceback.print_exc()
            self.emergency_land()
            return False
    
    def emergency_land(self):
        """Emergency landing procedure."""
        print(f"\n{'!'*70}")
        print(f"⚠️  EMERGENCY LANDING")
        print(f"{'!'*70}")
        
        try:
            # Land immediately
            print("🛬 Emergency landing...")
            self.airsim_client.landAsync().join()
            time.sleep(2)
            
            # Disarm
            self.airsim_client.armDisarm(False)
            self.airsim_client.enableApiControl(False)
            print("✅ Emergency landing complete")
            
            # Try to archive
            if self.flight_id:
                print("📦 Attempting to archive flight...")
                self.end_flight()
            
        except Exception as e:
            print(f"❌ Emergency landing error: {e}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main function."""
    try:
        print(f"\n{'='*70}")
        print(f"🚁 UAV CLIENT 2 - SQUARE PATTERN FLIGHT")
        print(f"Author: Muntasir Al Mamun (@Muntasir-Mamun7)")
        print(f"Date: 2025-11-03")
        print(f"Version: 3.0.0 - Testing Optimized")
        print(f"{'='*70}\n")
        
        # Create and run client
        client = UAVClient()
        success = client.run()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Program interrupted by user!")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()