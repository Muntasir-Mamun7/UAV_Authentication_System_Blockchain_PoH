"""
Smart Contracts System for UAV Authentication
Author: Muntasir Al Mamun
Date: 2025-10-25
"""

import time
from datetime import datetime

class SmartContract:
    """Base class for smart contracts"""
    
    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.enabled = True
        self.violations = []
        self.execution_count = 0
    
    def evaluate(self, data):
        """Override this method in subclasses"""
        raise NotImplementedError
    
    def execute(self, data):
        """Execute the contract"""
        if not self.enabled:
            return None
        
        self.execution_count += 1
        result = self.evaluate(data)
        
        if result:
            violation = {
                'contract': self.name,
                'timestamp': time.time(),
                'data': data,
                'result': result
            }
            self.violations.append(violation)
            return violation
        
        return None

class GeofenceContract(SmartContract):
    """Geofencing smart contract"""
    
    def __init__(self, max_x=50, max_y=50, min_altitude=-20, max_altitude=0):
        super().__init__(
            "Geofence Compliance",
            "Ensures UAV stays within allowed geographical boundaries"
        )
        self.max_x = max_x
        self.max_y = max_y
        self.min_altitude = min_altitude
        self.max_altitude = max_altitude
    
    def evaluate(self, data):
        x = data.get('x_pos', 0)
        y = data.get('y_pos', 0)
        z = data.get('z_alt', 0)
        
        violations = []
        
        if abs(x) > self.max_x:
            violations.append(f"X-axis violation: {x:.2f}m (limit: ±{self.max_x}m)")
        
        if abs(y) > self.max_y:
            violations.append(f"Y-axis violation: {y:.2f}m (limit: ±{self.max_y}m)")
        
        if z < self.min_altitude:
            violations.append(f"Altitude too low: {z:.2f}m (min: {self.min_altitude}m)")
        
        if z > self.max_altitude:
            violations.append(f"Altitude too high: {z:.2f}m (max: {self.max_altitude}m)")
        
        if violations:
            return {
                'severity': 'HIGH',
                'violations': violations,
                'position': (x, y, z)
            }
        
        return None

class SpeedLimitContract(SmartContract):
    """Speed limit enforcement contract"""
    
    def __init__(self, max_speed=10.0):
        super().__init__(
            "Speed Limit Enforcement",
            "Ensures UAV does not exceed maximum safe speed"
        )
        self.max_speed = max_speed
    
    def evaluate(self, data):
        speed = data.get('vel_mag', 0)
        
        if speed > self.max_speed:
            return {
                'severity': 'MEDIUM',
                'message': f"Speed limit exceeded: {speed:.2f} m/s (limit: {self.max_speed} m/s)",
                'speed': speed
            }
        
        return None

class AltitudeSafetyContract(SmartContract):
    """Altitude safety monitoring"""
    
    def __init__(self, warning_threshold=-3, critical_threshold=-1):
        super().__init__(
            "Altitude Safety Monitor",
            "Warns when UAV is flying too low"
        )
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
    
    def evaluate(self, data):
        altitude = data.get('z_alt', -10)
        
        if altitude > self.critical_threshold:
            return {
                'severity': 'CRITICAL',
                'message': f"CRITICAL: Altitude dangerously low: {altitude:.2f}m",
                'altitude': altitude
            }
        
        if altitude > self.warning_threshold:
            return {
                'severity': 'WARNING',
                'message': f"Warning: Low altitude detected: {altitude:.2f}m",
                'altitude': altitude
            }
        
        return None

class FlightDurationContract(SmartContract):
    """Flight duration monitoring"""
    
    def __init__(self, max_duration=120):  # 2 minutes
        super().__init__(
            "Flight Duration Limit",
            "Ensures flights do not exceed maximum duration"
        )
        self.max_duration = max_duration
        self.flight_start_times = {}
    
    def evaluate(self, data):
        flight_id = data.get('flight_id')
        current_time = time.time()
        
        if flight_id not in self.flight_start_times:
            self.flight_start_times[flight_id] = current_time
            return None
        
        duration = current_time - self.flight_start_times[flight_id]
        
        if duration > self.max_duration:
            return {
                'severity': 'MEDIUM',
                'message': f"Flight duration exceeded: {duration:.1f}s (limit: {self.max_duration}s)",
                'duration': duration
            }
        
        return None

class ContractManager:
    """Manages all smart contracts"""
    
    def __init__(self):
        self.contracts = []
        self.total_violations = 0
    
    def add_contract(self, contract):
        """Add a new contract"""
        self.contracts.append(contract)
        print(f"✅ Smart Contract Added: {contract.name}")
    
    def remove_contract(self, contract_name):
        """Remove a contract"""
        self.contracts = [c for c in self.contracts if c.name != contract_name]
    
    def evaluate_all(self, data):
        """Evaluate all contracts"""
        violations = []
        
        for contract in self.contracts:
            result = contract.execute(data)
            if result:
                violations.append(result)
                self.total_violations += 1
                self.log_violation(result)
        
        return violations
    
    def log_violation(self, violation):
        """Log a contract violation"""
        timestamp = datetime.fromtimestamp(violation['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"⚠️  Smart Contract Violation [{timestamp}]")
        print(f"   Contract: {violation['contract']}")
        print(f"   Details: {violation['result']}")
    
    def get_statistics(self):
        """Get contract statistics"""
        stats = {
            'total_contracts': len(self.contracts),
            'total_violations': self.total_violations,
            'contracts': []
        }
        
        for contract in self.contracts:
            stats['contracts'].append({
                'name': contract.name,
                'description': contract.description,
                'enabled': contract.enabled,
                'executions': contract.execution_count,
                'violations': len(contract.violations)
            })
        
        return stats