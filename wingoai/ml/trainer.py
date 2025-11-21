import os
import sys
from ml_engine import MLEngine, GAME_TYPE_CONFIG

def train_all_models():
    """Train all ML models for all game types"""
    ml_engine = MLEngine()
    success_count = 0
    total_games = len(GAME_TYPE_CONFIG)
    
    print("Training models for all game types...")
    
    for game_type in GAME_TYPE_CONFIG.keys():
        print(f"\nTraining {game_type} model...")
        success = ml_engine.train_model(game_type)
        if success:
            print(f"✅ {game_type} model trained successfully!")
            success_count += 1
        else:
            print(f"❌ {game_type} model training failed!")
    
    print(f"\nTraining complete: {success_count}/{total_games} models trained successfully!")

if __name__ == "__main__":
    train_all_models()