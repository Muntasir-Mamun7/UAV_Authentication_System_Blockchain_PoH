"""
Smart Landing Zone Selection
Author: Muntasir Al Mamun
Date: 2025-10-26
Prevents landing on trees, water, or unsafe surfaces
"""

import numpy as np
import random

class LandingZoneSelector:
    """Intelligent landing zone selection system"""
    
    def __init__(self, arena_size=50):
        self.arena_size = arena_size
        self.unsafe_zones = []
        self.safe_zones = []
        
        # Define unsafe zones (trees, water, obstacles)
        self._initialize_hazard_map()
    
    def _initialize_hazard_map(self):
        """Initialize known hazard locations"""
        # Example: Trees at specific locations
        self.unsafe_zones = [
            {'type': 'tree', 'x': 10, 'y': 10, 'radius': 3},
            {'type': 'tree', 'x': 25, 'y': 15, 'radius': 2.5},
            {'type': 'tree', 'x': 40, 'y': 30, 'radius': 4},
            {'type': 'water', 'x': 20, 'y': 40, 'radius': 8},
            {'type': 'water', 'x': 45, 'y': 45, 'radius': 5},
        ]
        
        # Define safe landing pads
        self.safe_zones = [
            {'x': 5, 'y': 5, 'radius': 3, 'priority': 'high'},
            {'x': 45, 'y': 5, 'radius': 3, 'priority': 'high'},
            {'x': 25, 'y': 25, 'radius': 4, 'priority': 'medium'},
        ]
    
    def is_safe_landing_zone(self, x, y, safety_radius=2.0):
        """Check if a position is safe for landing"""
        for hazard in self.unsafe_zones:
            distance = np.sqrt((x - hazard['x'])**2 + (y - hazard['y'])**2)
            if distance < (hazard['radius'] + safety_radius):
                return False, f"Too close to {hazard['type']}"
        
        return True, "Safe landing zone"
    
    def find_nearest_safe_zone(self, current_x, current_y):
        """Find the nearest safe landing zone"""
        best_zone = None
        min_distance = float('inf')
        
        # First, check designated safe zones
        for zone in self.safe_zones:
            distance = np.sqrt((current_x - zone['x'])**2 + (current_y - zone['y'])**2)
            if distance < min_distance:
                is_safe, _ = self.is_safe_landing_zone(zone['x'], zone['y'])
                if is_safe:
                    min_distance = distance
                    best_zone = {'x': zone['x'], 'y': zone['y'], 'type': 'designated'}
        
        # If no designated zone found, search for safe ground
        if best_zone is None:
            best_zone = self._search_for_safe_ground(current_x, current_y)
        
        return best_zone
    
    def _search_for_safe_ground(self, start_x, start_y, search_radius=10):
        """Search for safe ground near current position"""
        # Grid search for safe landing
        step = 2.0
        for radius in np.arange(0, search_radius, step):
            for angle in np.linspace(0, 2*np.pi, 12):
                test_x = start_x + radius * np.cos(angle)
                test_y = start_y + radius * np.sin(angle)
                
                # Check if within bounds
                if 0 <= test_x <= self.arena_size and 0 <= test_y <= self.arena_size:
                    is_safe, _ = self.is_safe_landing_zone(test_x, test_y)
                    if is_safe:
                        return {'x': test_x, 'y': test_y, 'type': 'found'}
        
        # Emergency: return start position if nothing found
        return {'x': start_x, 'y': start_y, 'type': 'emergency'}
    
    def get_landing_instructions(self, current_x, current_y, current_z):
        """Get smart landing instructions"""
        # Check current position
        is_safe, reason = self.is_safe_landing_zone(current_x, current_y)
        
        if is_safe:
            return {
                'action': 'land_here',
                'x': current_x,
                'y': current_y,
                'message': '✅ Current position is safe for landing'
            }
        else:
            # Find safe alternative
            safe_zone = self.find_nearest_safe_zone(current_x, current_y)
            distance = np.sqrt((current_x - safe_zone['x'])**2 + (current_y - safe_zone['y'])**2)
            
            return {
                'action': 'redirect',
                'x': safe_zone['x'],
                'y': safe_zone['y'],
                'distance': distance,
                'message': f'⚠️ Unsafe: {reason}. Redirecting to safe zone {distance:.1f}m away'
            }