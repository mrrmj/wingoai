import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib
import requests
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Game type mappings
GAME_TYPE_CONFIG = {
    '30sec': {
        'api_endpoint': 'WinGo_30S',
        'interval_seconds': 30
    },
    '1min': {
        'api_endpoint': 'WinGo_1M',
        'interval_seconds': 60
    },
    '3min': {
        'api_endpoint': 'WinGo_3M',
        'interval_seconds': 180
    },
    '5min': {
        'api_endpoint': 'WinGo_5M',
        'interval_seconds': 300
    }
}

class MLEngine:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.label_encoder = LabelEncoder()
        self.models_dir = "ml/models"
        os.makedirs(self.models_dir, exist_ok=True)
        
    def fetch_history(self, game_type, pages=50):
        """Fetch prediction history from API for specific game type"""
        if game_type not in GAME_TYPE_CONFIG:
            raise ValueError(f"Invalid game type: {game_type}")
            
        endpoint = GAME_TYPE_CONFIG[game_type]['api_endpoint']
        history = []
        for page in range(1, pages + 1):
            try:
                url = f"https://draw.ar-lottery01.com/WinGo/{endpoint}/GetHistoryIssuePage.json?pageNo={page}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and 'list' in data['data']:
                        history.extend(data['data']['list'])
            except Exception as e:
                print(f"Error fetching {game_type} page {page}: {e}")
                continue
        return history

    def prepare_features(self, history_data):
        """Prepare features from history data"""
        df = pd.DataFrame(history_data)
        if df.empty:
            return pd.DataFrame()
            
        # Sort by issue number to ensure chronological order
        df = df.sort_values('issueNumber').reset_index(drop=True)
        
        # Convert number to numeric if needed
        df['number'] = pd.to_numeric(df['number'], errors='coerce')
        
        # Feature engineering
        features = pd.DataFrame()
        features['issueNumber'] = df['issueNumber']
        features['number'] = df['number']
        
        # Color features
        features['color_encoded'] = self.label_encoder.fit_transform(df['color'])
        
        # Last N outcomes features
        for i in range(1, 6):  # Last 5 rounds
            features[f'prev_color_{i}'] = df['color'].shift(i).apply(
                lambda x: self.label_encoder.transform([x])[0] if x in self.label_encoder.classes_ else -1
            )
            features[f'prev_number_{i}'] = df['number'].shift(i)
        
        # Streak features
        features['streak_red'] = self._calculate_streak(df['color'], 'RED')
        features['streak_green'] = self._calculate_streak(df['color'], 'GREEN')
        features['streak_violet'] = self._calculate_streak(df['color'], 'VIOLET')
        
        # Color frequency in last 10 rounds - FIXED VERSION
        # Create numeric mapping for colors to use in rolling operations
        color_map = {'RED': 1, 'GREEN': 2, 'VIOLET': 3}
        df['color_numeric'] = df['color'].apply(lambda x: color_map.get(x, 0))
        
        for color in ['RED', 'GREEN', 'VIOLET']:
            color_code = color_map[color]
            features[f'freq_{color}_last10'] = df['color_numeric'].rolling(window=10).apply(
                lambda x: (x == color_code).sum() if len(x) == 10 else np.nan,
                raw=True  # Use raw=True for faster numeric operations
            )
        
        # Parity features
        features['is_even'] = (df['number'] % 2 == 0).astype(int)
        features['parity_streak'] = self._calculate_parity_streak(df['number'])
        
        # Big/small features (assuming >50 is big)
        features['is_big'] = (df['number'] > 50).astype(int)
        features['big_streak'] = self._calculate_big_small_streak(df['number'], 'big')
        
        # Moving averages
        features['ma_5'] = df['number'].rolling(window=5).mean()
        features['ma_10'] = df['number'].rolling(window=10).mean()
        
        # Deltas
        features['delta_1'] = df['number'].diff(1)
        features['delta_2'] = df['number'].diff(2)
        
        # Drop rows with NaN values
        features = features.dropna()
        
        # Prepare target variable (next color)
        targets = df['color'].iloc[1:].reset_index(drop=True)
        features = features.iloc[:-1].reset_index(drop=True)
        
        return features, targets

    def _calculate_streak(self, series, color):
        """Calculate consecutive streaks for a specific color"""
        streaks = []
        current_streak = 0
        
        for val in series:
            if val == color:
                current_streak += 1
            else:
                current_streak = 0
            streaks.append(current_streak)
        
        return streaks

    def _calculate_parity_streak(self, numbers):
        """Calculate consecutive parity streaks"""
        streaks = []
        current_streak = 0
        last_parity = None
        
        for num in numbers:
            if pd.isna(num):
                streaks.append(0)
                continue
                
            parity = 'even' if num % 2 == 0 else 'odd'
            if parity == last_parity:
                current_streak += 1
            else:
                current_streak = 1
            last_parity = parity
            streaks.append(current_streak)
        
        return streaks

    def _calculate_big_small_streak(self, numbers, category):
        """Calculate big/small streaks"""
        streaks = []
        current_streak = 0
        last_category = None
        
        for num in numbers:
            if pd.isna(num):
                streaks.append(0)
                continue
                
            cat = 'big' if num > 50 else 'small'
            if cat == last_category:
                current_streak += 1
            else:
                current_streak = 1
            last_category = cat
            streaks.append(current_streak)
        
        return streaks

    def train_model(self, game_type):
        """Train the ML model for specific game type"""
        print(f"Fetching {game_type} history data...")
        history = self.fetch_history(game_type, pages=50)
        
        if len(history) < 100:
            print(f"Not enough data to train {game_type} model")
            return False
            
        print(f"Fetched {len(history)} {game_type} records")
        
        features, targets = self.prepare_features(history)
        
        if features.empty or len(features) != len(targets):
            print(f"Not enough features or mismatch in {game_type} data")
            return False
            
        print(f"{game_type} Features shape: {features.shape}")
        
        # Prepare features for training (exclude issueNumber and other non-feature columns)
        feature_cols = [col for col in features.columns if col not in ['issueNumber']]
        X = features[feature_cols]
        y = self.label_encoder.fit_transform(targets)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train model
        self.model.fit(X_train, y_train)
        
        # Evaluate
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)
        
        print(f"{game_type} Training score: {train_score:.3f}")
        print(f"{game_type} Test score: {test_score:.3f}")
        
        # Save model with game type suffix
        joblib.dump(self.model, os.path.join(self.models_dir, f'rf_model_{game_type}.pkl'))
        joblib.dump(self.label_encoder, os.path.join(self.models_dir, f'label_encoder_{game_type}.pkl'))
        
        return True

    def load_model(self, game_type):
        """Load trained model for specific game type"""
        try:
            model_path = os.path.join(self.models_dir, f'rf_model_{game_type}.pkl')
            encoder_path = os.path.join(self.models_dir, f'label_encoder_{game_type}.pkl')
            
            if os.path.exists(model_path) and os.path.exists(encoder_path):
                self.model = joblib.load(model_path)
                self.label_encoder = joblib.load(encoder_path)
                return True
            else:
                return False
        except Exception as e:
            print(f"Error loading {game_type} model: {e}")
            return False

    def predict_next(self, game_type, history_data):
        """Predict next outcome for specific game type"""
        if not self.load_model(game_type):
            print(f"{game_type} model not found, training new model...")
            if not self.train_model(game_type):
                return None, 0.0
        
        features, _ = self.prepare_features(history_data[-20:])  # Use last 20 rounds for prediction
        
        if features.empty:
            return None, 0.0
            
        # Prepare features for prediction
        feature_cols = [col for col in features.columns if col not in ['issueNumber']]
        X = features[feature_cols].tail(1)  # Last row for prediction
        
        if X.empty:
            return None, 0.0
            
        # Make prediction
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]
        
        predicted_color = self.label_encoder.inverse_transform([prediction])[0]
        confidence = max(probabilities)
        
        return predicted_color, confidence
