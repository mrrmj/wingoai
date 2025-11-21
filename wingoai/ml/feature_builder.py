import pandas as pd
import numpy as np

def build_features(history_data):
    """Build features from historical data"""
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
    color_map = {'RED': 0, 'GREEN': 1, 'VIOLET': 2}
    features['color_encoded'] = df['color'].map(color_map)
    
    # Last N outcomes features
    for i in range(1, 6):  # Last 5 rounds
        features[f'prev_color_{i}'] = df['color'].shift(i).map(color_map)
        features[f'prev_number_{i}'] = df['number'].shift(i)
    
    # Streak features
    features['streak_red'] = calculate_streak(df['color'], 'RED')
    features['streak_green'] = calculate_streak(df['color'], 'GREEN')
    features['streak_violet'] = calculate_streak(df['color'], 'VIOLET')
    
    # Color frequency in last 10 rounds
    for color in ['RED', 'GREEN', 'VIOLET']:
        features[f'freq_{color}_last10'] = df['color'].rolling(window=10).apply(
            lambda x: (x == color).sum() if len(x) == 10 else np.nan
        )
    
    # Parity features
    features['is_even'] = (df['number'] % 2 == 0).astype(int)
    features['parity_streak'] = calculate_parity_streak(df['number'])
    
    # Big/small features (assuming >50 is big)
    features['is_big'] = (df['number'] > 50).astype(int)
    features['big_streak'] = calculate_big_small_streak(df['number'], 'big')
    
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

def calculate_streak(series, color):
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

def calculate_parity_streak(numbers):
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

def calculate_big_small_streak(numbers, category):
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