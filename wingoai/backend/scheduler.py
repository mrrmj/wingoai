from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from .ml_engine import MLEngine, GAME_TYPE_CONFIG
from .database import get_db
from .models import Prediction
from datetime import datetime
import asyncio
import json
import requests
import time

class PredictionScheduler:
    def __init__(self, websocket_manager):
        self.scheduler = BackgroundScheduler()
        self.ml_engine = MLEngine()
        self.websocket_manager = websocket_manager
        self.setup_jobs()

    def setup_jobs(self):
        # Schedule prediction jobs for each game type
        for game_type, config in GAME_TYPE_CONFIG.items():
            self.scheduler.add_job(
                self.run_prediction,
                trigger=IntervalTrigger(seconds=config['interval_seconds']),
                args=[game_type],
                id=f'prediction_job_{game_type}',
                name=f'Run {game_type} prediction every {config["interval_seconds"]} seconds',
                replace_existing=True
            )
        
        # Schedule model retraining daily for all game types
        self.scheduler.add_job(
            self.retrain_all_models,
            trigger='interval',
            hours=24,
            id='retrain_all_job',
            name='Retrain all models daily',
            replace_existing=True
        )

    def start(self):
        self.scheduler.start()
        print("Scheduler started with multi-game support...")

    def shutdown(self):
        self.scheduler.shutdown()
        print("Scheduler stopped...")

    def fetch_history(self, game_type):
        """Fetch recent history from API for specific game type"""
        if game_type not in GAME_TYPE_CONFIG:
            raise ValueError(f"Invalid game type: {game_type}")
            
        history = []
        for page in range(1, 6):  # Get last 5 pages
            try:
                endpoint = GAME_TYPE_CONFIG[game_type]['api_endpoint']
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

    def run_prediction(self, game_type):
        """Run prediction and store results for specific game type"""
        print(f"Running {game_type} prediction...")
        
        # Fetch recent history
        history = self.fetch_history(game_type)
        
        if len(history) < 50:
            print(f"Not enough {game_type} history data for prediction")
            return
        
        # Make prediction using ML
        predicted_color, confidence = self.ml_engine.predict_next(game_type, history)
        
        if predicted_color is None:
            print(f"{game_type} prediction failed")
            return
        
        # Determine if it's safe to play
        safe = confidence >= 0.80
        
        # Store prediction in database
        db = get_db()
        try:
            prediction = Prediction(
                game_type=game_type,
                period=history[0]['issueNumber'] if history else str(int(time.time())),
                color=predicted_color,
                confidence=confidence,
                safe=safe,
                model=f'ensemble_rf_{game_type}'
            )
            db.add(prediction)
            db.commit()
            
            # Broadcast to WebSocket clients
            prediction_data = {
                "game_type": prediction.game_type,
                "period": prediction.period,
                "color": prediction.color,
                "confidence": prediction.confidence,
                "safe": prediction.safe,
                "model": prediction.model,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            asyncio.run(self.websocket_manager.broadcast_prediction(prediction_data))
            print(f"{game_type} Prediction: {predicted_color}, Confidence: {confidence:.2f}, Safe: {safe}")
            
        except Exception as e:
            print(f"Error storing {game_type} prediction: {e}")
            db.rollback()
        finally:
            db.close()

    def retrain_all_models(self):
        """Retrain all ML models"""
        print("Retraining all models...")
        for game_type in GAME_TYPE_CONFIG.keys():
            success = self.ml_engine.train_model(game_type)
            if success:
                print(f"{game_type} model retrained successfully")
            else:
                print(f"{game_type} model retraining failed")