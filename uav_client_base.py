"""
UAV Client Base - AirSim Integration
Author: Muntasir Al Mamun (@Muntasir-Mamun7)
Date: 2025-10-26
Version: 3.0.0 - AirSim Drone Control
"""

import requests
import time
import hashlib
import json
import math
import threading

# Import AirSim
try:
    import airsim
    AIRSIM_AVAILABLE = True
    print("✅ AirSim library imported successfully")
except ImportError:
    AIRSIM_AVAILABLE = False
    print("⚠️  AirSim not found. Install with: pip install airsim")

# Try to import smart landing (optional)
try:
    from smart_landing import LandingZoneSelector
    SMART_LANDING_AVAILABLE = True
except ImportError:
    SMART_LANDING_AVAILABLE = False


class AirSimDrone:
    """AirSim drone controller."""
    
    def __init__(self, vehicle_name="Drone1"):
        """Initialize AirSim drone connection."""
        if not AIRSIM_AVAILABLE:
            raise ImportError("AirSim not installed. Run: pip install airsim")
        
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()
        self.client.enableApiControl(True, vehicle_name)
        self.client.armDisarm(True, vehicle_name)
        self.vehicle_name = vehicle_name
        
        print(f"✅ Connected to AirSim - Vehicle: {vehicle_name}")
    
    def takeoff(self, altitude=10.0):
        """Takeoff to specified altitude."""
        print(f"🛫 Taking off to {altitude}m...")
        self.client.takeoffAsync(vehicle_name=self.vehicle_name).join()
        
        # Move to altitude
        self.client.moveToZAsync(-altitude, velocity=2, vehicle_name=self.vehicle_name).join()
        time.sleep(1)
        print(f"✅ Reached altitude {altitude}m")
    
    def goto(self, target, velocity=4.0):
        """Fly to target position [x, y, z]."""
        target_x, target_y, target_z = target
        
        # Calculate distance
        state = self.client.getMultirotorState(vehicle_name=self.vehicle_name)
        current_pos = state.kinematics_estimated.position
        
        dx = target_x - current_pos.x_val
        dy = target_y - current_pos.y_val
        dz = target_z - current_pos.z_val
        distance = math.sqrt(dx**2 + dy**2 + dz**2)
        
        print(f"🎯 Flying to ({target_x:.1f}, {target_y:.1f}, {abs(target_z):.1f}m altitude) - Distance: {distance:.1f}m")
        
        # Move to position
        self.client.moveToPositionAsync(
            target_x, target_y, target_z, 
            velocity, 
            vehicle_name=self.vehicle_name
        ).join()
        
        print(f"✅ Arrived at waypoint")
    
    def land(self):
        """Land the drone."""
        print("🛬 Landing...")
        self.client.landAsync(vehicle_name=self.vehicle_name).join()
        time.sleep(2)
        print("✅ Landed")
    
    def get_position(self):
        """Get current position."""
        state = self.client.getMultirotorState(vehicle_name=self.vehicle_name)
        pos = state.kinematics_estimated.position
        
        return {
            'x': pos.x_val,
            'y': pos.y_val,
            'z': pos.z_val
        }
    
    def get_velocity(self):
        """Get current velocity."""
        state = self.client.getMultirotorState(vehicle_name=self.vehicle_name)
        vel = state.kinematics_estimated.linear_velocity
        
        magnitude = math.sqrt(vel.x_val**2 + vel.y_val**2 + vel.z_val**2)
        
        return {
            'x': vel.x_val,
            'y': vel.y_val,
            'z': vel.z_val,
            'magnitude': magnitude
        }
    
    def reset(self):
        """Reset drone to initial state."""
        self.client.reset()
        self.client.enableApiControl(True, self.vehicle_name)
        self.client.armDisarm(True, self.vehicle_name)


class UAVClientBase:
    """Base class for UAV clients with blockchain integration."""
    
    def __init__(self, uav_id, uav_supi, long_term_key, flight_duration=60, 
                 api_base='http://127.0.0.1:5000/api', vehicle_name="Drone1"):
        """
        Initialize UAV Client.
        
        Args:
            uav_id: Unique UAV identifier
            uav_supi: UAV Subscriber Permanent Identifier
            long_term_key: Pre-shared long-term key
            flight_duration: Flight duration in seconds
            api_base: GCS API base URL
            vehicle_name: AirSim vehicle name
        """
        self.uav_id = uav_id
        self.uav_supi = uav_supi
        self.long_term_key = long_term_key
        self.flight_duration = flight_duration
        self.api_base = api_base
        
        self.flight_id = None
        self.session_key = None
        self.authenticated = False
        
        # Initialize AirSim drone
        try:
            self.drone = AirSimDrone(vehicle_name=vehicle_name)
        except Exception as e:
            print(f"❌ Failed to connect to AirSim: {e}")
            print("⚠️  Make sure AirSim/Unreal Engine is running!")
            raise
        
        # Initialize Smart Landing (if available)
        if SMART_LANDING_AVAILABLE:
            self.landing_selector = LandingZoneSelector()
            print("✅ Smart Landing System Initialized")
        else:
            self.landing_selector = None
        
        # Flight state
        self.flight_active = False
        self.start_time = None
        self.telemetry_thread = None
        self.stop_telemetry = False
    
    # =========================================================================
    # FLIGHT INITIALIZATION
    # =========================================================================
    
    def start_flight(self):
        """Start a new flight and create blockchain."""
        try:
            response = requests.post(f"{self.api_base}/start_flight", json={
                'uav_supi': self.uav_supi
            }, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.flight_id = data['flight_id']
                self.start_time = time.time()
                self.flight_active = True
                print(f"✈️  Flight {self.flight_id} started")
                print(f"🔗 Genesis Hash: {data['genesis_hash'][:16]}...")
                return True
            else:
                print(f"❌ Failed to start flight: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting flight: {e}")
            return False
    
    # =========================================================================
    # AUTHENTICATION (5G-AKA Simulation)
    # =========================================================================
    
    def authenticate(self):
        """Perform 5G-AKA authentication with GCS."""
        try:
            # Step 1: Request authentication challenge
            response = requests.post(f"{self.api_base}/authenticate", json={
                'flight_id': self.flight_id,
                'uav_supi': self.uav_supi,
                'step': 1
            }, timeout=5)
            
            if response.status_code != 200:
                print(f"❌ Authentication challenge failed: {response.text}")
                return False
            
            challenge = response.json()
            rand = challenge['rand']
            
            # Step 2: Calculate response (RES*)
            res_star = self.calculate_res_star(rand)
            
            # Step 3: Send response to GCS
            response = requests.post(f"{self.api_base}/authenticate", json={
                'flight_id': self.flight_id,
                'uav_supi': self.uav_supi,
                'step': 2,
                'res_star': res_star
            }, timeout=5)
            
            if response.status_code == 200:
                auth_result = response.json()
                if auth_result['status'] == 'AUTH_SUCCESS':
                    self.session_key = auth_result['session_key']
                    self.authenticated = True
                    print(f"🔐 Authenticated | Session Key: {self.session_key[:16]}...")
                    return True
                else:
                    print(f"❌ Authentication failed: {auth_result.get('reason', 'Unknown')}")
                    return False
            else:
                print(f"❌ Authentication verification failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
    
    def calculate_res_star(self, rand):
        """Calculate RES* from challenge."""
        xres_data = (self.long_term_key + str(rand) + 'Expected').encode('utf-8')
        return hashlib.sha256(xres_data).hexdigest()[:10]
    
    # =========================================================================
    # TELEMETRY LOGGING
    # =========================================================================
    
    def log_telemetry(self):
        """Log current telemetry to blockchain."""
        if not self.authenticated:
            return False
        
        try:
            # Get current position and velocity from AirSim
            position = self.drone.get_position()
            velocity = self.drone.get_velocity()
            
            telemetry = {
                'x_pos': position['x'],
                'y_pos': position['y'],
                'z_alt': position['z'],
                'vel_mag': velocity['magnitude'],
                'timestamp': time.time()
            }
            
            # Send to GCS
            response = requests.post(f"{self.api_base}/log_telemetry", json={
                'flight_id': self.flight_id,
                'telemetry': telemetry,
                'tx_id': f'TELEM_{self.uav_id}_{int(time.time() * 1000)}'
            }, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                
                # Check for smart contract violations
                if result.get('violations'):
                    for violation in result['violations']:
                        print(f"⚠️  {violation['contract']}: {violation['message']}")
                
                # Check for anomalies
                if result.get('anomaly', {}).get('anomaly'):
                    anomaly = result['anomaly']
                    # Only show HIGH and CRITICAL anomalies to reduce noise
                    if anomaly.get('severity') in ['HIGH', 'CRITICAL']:
                        print(f"🚨 ANOMALY - Severity: {anomaly.get('severity')}")
                
                # Block mined notification
                if result['status'] == 'TX_BLOCK_ACK':
                    print(f"📦 Block mined | Hash: {result['hash']}...")
                
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    def telemetry_logger_thread(self):
        """Background thread for continuous telemetry logging."""
        log_interval = 1  # Log every 1 second
        
        while not self.stop_telemetry and self.flight_active:
            self.log_telemetry()
            
            # Show countdown
            elapsed = time.time() - self.start_time
            remaining = self.flight_duration - elapsed
            
            if remaining > 0 and int(remaining) % 10 == 0 and int(remaining) != self.flight_duration:
                print(f"⏳ {int(remaining)}s remaining...")
            
            time.sleep(log_interval)
    
    # =========================================================================
    # FLIGHT EXECUTION
    # =========================================================================
    
    def execute_flight_pattern(self):
        """
        Execute flight pattern. Override in subclasses.
        Default: Square pattern.
        """
        print("🛫 Executing square flight pattern...")
        
        # Takeoff
        self.drone.takeoff(altitude=10.0)
        
        # Square pattern waypoints
        waypoints = [
            [20, 0, -10],
            [20, 20, -10],
            [0, 20, -10],
            [0, 0, -10]
        ]
        
        for i, waypoint in enumerate(waypoints, 1):
            print(f"📍 Waypoint {i}/4")
            self.drone.goto(waypoint, velocity=4.0)
    
    def run(self):
        """Main flight execution loop."""
        print(f"\n{'='*60}")
        print(f"🚁 UAV Client - {self.uav_id}")
        print(f"📋 SUPI: {self.uav_supi}")
        print(f"⏱️  Duration: {self.flight_duration}s")
        print(f"🔗 GCS API: {self.api_base}")
        print(f"{'='*60}\n")
        
        # Step 1: Start flight
        if not self.start_flight():
            print("❌ Flight start failed. Aborting.")
            return False
        
        time.sleep(0.5)
        
        # Step 2: Authenticate
        if not self.authenticate():
            print("❌ Authentication failed. Aborting.")
            self.emergency_shutdown()
            return False
        
        time.sleep(0.5)
        
        # Step 3: Start telemetry logging thread
        print(f"\n📡 Starting telemetry logging (every 1s for {self.flight_duration}s)...\n")
        self.stop_telemetry = False
        self.telemetry_thread = threading.Thread(target=self.telemetry_logger_thread, daemon=True)
        self.telemetry_thread.start()
        
        # Step 4: Execute flight pattern
        try:
            self.execute_flight_pattern()
            
            # Step 5: Wait for remaining flight duration
            elapsed = time.time() - self.start_time
            remaining = max(0, self.flight_duration - elapsed)
            
            if remaining > 0:
                print(f"\n⏳ Hovering for {int(remaining)}s...")
                time.sleep(remaining)
            
            # Stop telemetry logging
            self.stop_telemetry = True
            if self.telemetry_thread:
                self.telemetry_thread.join(timeout=2)
            
            # Step 6: Smart Landing
            print(f"\n{'='*60}")
            print("🛬 Initiating landing sequence...")
            print(f"{'='*60}")
            
            self.execute_smart_landing()
            
        except KeyboardInterrupt:
            print("\n⚠️  Flight interrupted by user!")
            self.stop_telemetry = True
            self.emergency_shutdown()
            return False
        except Exception as e:
            print(f"\n❌ Flight error: {e}")
            import traceback
            traceback.print_exc()
            self.stop_telemetry = True
            self.emergency_shutdown()
            return False
        
        # Step 7: End flight and archive
        self.end_flight()
        
        print(f"\n{'='*60}")
        print(f"✅ Flight {self.flight_id} completed successfully")
        print(f"{'='*60}\n")
        
        return True
    
    # =========================================================================
    # SMART LANDING
    # =========================================================================
    
    def execute_smart_landing(self):
        """Execute smart landing with safety checks."""
        if not SMART_LANDING_AVAILABLE or self.landing_selector is None:
            # Fallback to simple landing
            print("🛬 Landing at current position...")
            self.drone.land()
            return
        
        # Get current position
        current_pos = self.drone.get_position()
        x, y, z = current_pos['x'], current_pos['y'], current_pos['z']
        
        print(f"📍 Current position: ({x:.2f}, {y:.2f}, {abs(z):.2f}m altitude)")
        
        # Get smart landing instructions
        instructions = self.landing_selector.get_landing_instructions(x, y, z)
        
        print(instructions['message'])
        
        if instructions['action'] == 'redirect':
            # Need to fly to safe zone first
            safe_x = instructions['x']
            safe_y = instructions['y']
            distance = instructions['distance']
            
            print(f"🔄 Redirecting to safe landing zone ({safe_x:.1f}, {safe_y:.1f})")
            print(f"📏 Distance: {distance:.1f}m")
            
            # Fly to safe zone
            self.drone.goto([safe_x, safe_y, z], velocity=2.0)
            
            # Verify arrival
            new_pos = self.drone.get_position()
            print(f"✅ Arrived at safe zone: ({new_pos['x']:.2f}, {new_pos['y']:.2f})")
        
        # Execute landing
        print("🛬 Landing at safe zone...")
        self.drone.land()
        print("✅ Landed safely")
    
    # =========================================================================
    # FLIGHT TERMINATION
    # =========================================================================
    
    def end_flight(self):
        """End the flight and archive blockchain."""
        if not self.flight_id:
            return
        
        try:
            response = requests.post(f"{self.api_base}/end_flight", json={
                'flight_id': self.flight_id
            }, timeout=10)  # Increased timeout
            
            if response.status_code == 200:
                print(f"📦 Flight {self.flight_id} archived successfully")
                self.flight_active = False
                return True
            else:
                print(f"⚠️  Failed to archive flight: {response.text}")
                return False
                
        except Exception as e:
            print(f"⚠️  Error ending flight: {e}")
            return False
    
    def emergency_shutdown(self):
        """Emergency shutdown procedure."""
        print("\n" + "!"*60)
        print("⚠️  EMERGENCY SHUTDOWN")
        print("!"*60)
        
        try:
            # Stop telemetry
            self.stop_telemetry = True
            
            # Emergency land
            print("🛬 Emergency landing...")
            self.drone.land()
            
            # Try to end flight gracefully
            if self.flight_id:
                print("📦 Archiving flight data...")
                self.end_flight()
            
            print("✅ Emergency shutdown complete")
            
        except Exception as e:
            print(f"❌ Emergency shutdown error: {e}")


# =============================================================================
# SPECIFIC FLIGHT PATTERN IMPLEMENTATIONS
# =============================================================================

class SquarePatternUAV(UAVClientBase):
    """UAV that flies a square pattern."""
    
    def execute_flight_pattern(self):
        """Execute square flight pattern."""
        print("🛫 Square Pattern (20m x 20m)\n")
        
        self.drone.takeoff(altitude=10.0)
        
        waypoints = [
            [20, 0, -10],
            [20, 20, -10],
            [0, 20, -10],
            [0, 0, -10]
        ]
        
        for i, wp in enumerate(waypoints, 1):
            print(f"\n📍 Waypoint {i}/4")
            self.drone.goto(wp, velocity=4.0)


class CircularPatternUAV(UAVClientBase):
    """UAV that flies a circular pattern."""
    
    def execute_flight_pattern(self):
        """Execute circular flight pattern."""
        print("🛫 Circular Pattern (radius 15m)\n")
        
        self.drone.takeoff(altitude=10.0)
        
        # Circle with 8 points
        radius = 15
        center_x, center_y = 15, 15
        
        for i in range(8):
            angle = (2 * math.pi * i) / 8
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            
            print(f"\n📍 Waypoint {i+1}/8")
            self.drone.goto([x, y, -10], velocity=4.0)


class FigureEightPatternUAV(UAVClientBase):
    """UAV that flies a figure-eight pattern."""
    
    def execute_flight_pattern(self):
        """Execute figure-eight flight pattern."""
        print("🛫 Figure-Eight Pattern\n")
        
        self.drone.takeoff(altitude=10.0)
        
        radius = 10
        center_x, center_y = 15, 15
        
        for i in range(16):
            t = (2 * math.pi * i) / 16
            x = center_x + radius * math.sin(t)
            y = center_y + radius * math.sin(t) * math.cos(t)
            
            print(f"\n📍 Waypoint {i+1}/16")
            self.drone.goto([x, y, -10], velocity=4.0)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("⚠️  This is the base UAV client module.")
    print("   Use UAV_Client_1.py, UAV_Client_2.py, etc. to run flights.")
    print("="*70 + "\n")