"""
AI-Powered Anomaly Detection for UAV Flight Data
Author: Muntasir Al Mamun
Date: 2025-10-25
"""

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import json
import os
import pickle

class AnomalyDetector:
    """AI-based anomaly detection for UAV flights"""
    
    def __init__(self, model_path='models/anomaly_detector.pkl'):
        self.model = IsolationForest(
            contamination=0.1,  # Expected percentage of anomalies
            random_state=42,
            n_estimators=100
        )
        self.scaler = StandardScaler()
        self.trained = False
        self.model_path = model_path
        self.training_data = []
        
        # Ensure model directory exists
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Load existing model if available
        self.load_model()
    
    def extract_features(self, flight_data):
        """Extract numerical features from flight data"""
        features = []
        
        if isinstance(flight_data, list):
            # Multiple flights
            for flight in flight_data:
                features.append(self._extract_single_flight_features(flight))
        else:
            # Single data point - use same feature structure as training
            features.append(self._extract_single_point_features_padded(flight_data))
        
        return np.array(features)
    
    def _extract_single_point_features_padded(self, data):
        """
        Extract features from a single telemetry point
        Pads to match training feature count (6 features)
        """
        x = data.get('x_pos', 0)
        y = data.get('y_pos', 0)
        z = abs(data.get('z_alt', 0))
        speed = data.get('vel_mag', 0)
        
        # Return 6 features to match training data
        # [x, y, altitude, speed, speed (duplicate for consistency), distance_estimate]
        distance_estimate = np.sqrt(x**2 + y**2)  # Distance from origin
        
        return [
            x,                  # Feature 0: X position
            y,                  # Feature 1: Y position  
            z,                  # Feature 2: Altitude
            speed,              # Feature 3: Current speed
            speed,              # Feature 4: Speed (duplicate for compatibility)
            distance_estimate   # Feature 5: Distance from origin
        ]
    
    def _extract_single_flight_features(self, flight):
        """Extract features from an entire flight"""
        speeds = []
        altitudes = []
        distances = []
        
        prev_x, prev_y = None, None
        
        for block in flight.get('chain', []):
            for tx in block.get('transactions', []):
                if tx.get('data') and 'x_pos' in tx['data']:
                    data = tx['data']
                    speeds.append(data.get('vel_mag', 0))
                    altitudes.append(abs(data.get('z_alt', 0)))
                    
                    # Calculate distance traveled
                    if prev_x is not None:
                        dist = np.sqrt(
                            (data['x_pos'] - prev_x)**2 + 
                            (data['y_pos'] - prev_y)**2
                        )
                        distances.append(dist)
                    
                    prev_x = data['x_pos']
                    prev_y = data['y_pos']
        
        if not speeds:
            return [0, 0, 0, 0, 0, 0]
        
        return [
            np.mean(speeds),           # Average speed
            np.max(speeds),            # Max speed
            np.std(speeds),            # Speed variance
            np.mean(altitudes),        # Average altitude
            np.max(altitudes),         # Max altitude
            sum(distances) if distances else 0  # Total distance
        ]
    
    def train(self, historical_flights):
        """Train the anomaly detection model"""
        if len(historical_flights) < 5:
            print("⚠️  Not enough training data (minimum 5 flights required)")
            return False
        
        print(f"🤖 Training anomaly detector on {len(historical_flights)} flights...")
        
        features = self.extract_features(historical_flights)
        
        # Standardize features
        features_scaled = self.scaler.fit_transform(features)
        
        # Train the model
        self.model.fit(features_scaled)
        self.trained = True
        self.training_data = historical_flights
        
        # Save the model
        self.save_model()
        
        print("✅ Anomaly detection model trained successfully")
        return True
    
    def detect_realtime(self, telemetry_data):
        """Detect anomalies in real-time telemetry"""
        if not self.trained:
            return {'anomaly': False, 'reason': 'Model not trained yet'}
        
        try:
            features = self.extract_features(telemetry_data)
            features_scaled = self.scaler.transform(features)
            
            prediction = self.model.predict(features_scaled)
            score = self.model.score_samples(features_scaled)
            
            is_anomaly = prediction[0] == -1
            
            if is_anomaly:
                anomaly_score = float(score[0])
                
                # Analyze what makes it anomalous
                reasons = self._analyze_anomaly(telemetry_data)
                
                return {
                    'anomaly': True,
                    'score': anomaly_score,
                    'severity': self._get_severity(anomaly_score),
                    'reasons': reasons,
                    'timestamp': telemetry_data.get('timestamp', 0)
                }
            
            return {'anomaly': False}
        except Exception as e:
            print(f"⚠️  Anomaly detection error: {e}")
            return {'anomaly': False, 'error': str(e)}
    
    def detect_flight(self, flight_data):
        """Detect anomalies in an entire flight"""
        if not self.trained:
            return {'anomaly': False, 'reason': 'Model not trained yet'}
        
        features = self.extract_features([flight_data])
        features_scaled = self.scaler.transform(features)
        
        prediction = self.model.predict(features_scaled)
        score = self.model.score_samples(features_scaled)
        
        is_anomaly = prediction[0] == -1
        
        if is_anomaly:
            return {
                'anomaly': True,
                'score': float(score[0]),
                'severity': self._get_severity(score[0]),
                'message': 'Flight pattern deviates from normal behavior'
            }
        
        return {'anomaly': False, 'message': 'Flight pattern is normal'}
    
    def _analyze_anomaly(self, data):
        """Analyze what makes the data anomalous"""
        reasons = []
        
        # Check speed
        speed = data.get('vel_mag', 0)
        if speed > 10:
            reasons.append(f"Unusually high speed: {speed:.2f} m/s")
        elif speed < 0.5:
            reasons.append(f"Unusually low speed: {speed:.2f} m/s")
        
        # Check altitude
        altitude = abs(data.get('z_alt', 0))
        if altitude > 18:
            reasons.append(f"Unusually high altitude: {altitude:.2f} m")
        elif altitude < 5:
            reasons.append(f"Unusually low altitude: {altitude:.2f} m")
        
        # Check position
        x = data.get('x_pos', 0)
        y = data.get('y_pos', 0)
        if abs(x) > 100 or abs(y) > 100:
            reasons.append(f"Unusual position: ({x:.1f}, {y:.1f})")
        
        if not reasons:
            reasons.append("Pattern deviates from learned normal behavior")
        
        return reasons
    
    def _get_severity(self, score):
        """Determine severity based on anomaly score"""
        if score < -0.2:
            return 'CRITICAL'
        elif score < -0.1:
            return 'HIGH'
        elif score < 0:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def save_model(self):
        """Save the trained model to disk"""
        if not self.trained:
            return False
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'trained': self.trained
        }
        
        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"💾 Model saved to {self.model_path}")
        return True
    
    def load_model(self):
        """Load a trained model from disk"""
        if not os.path.exists(self.model_path):
            return False
        
        try:
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.trained = model_data['trained']
            
            print(f"✅ Anomaly detection model loaded from {self.model_path}")
            return True
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False
    
    def get_statistics(self):
        """Get detector statistics"""
        return {
            'trained': self.trained,
            'training_samples': len(self.training_data),
            'model_type': 'Isolation Forest',
            'contamination': 0.1
        }