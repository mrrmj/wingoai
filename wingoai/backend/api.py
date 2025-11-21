from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from .database import get_db, init_db
from .models import User, VerifyRequest, Prediction, Setting
from .scheduler import PredictionScheduler
from .ml_engine import MLEngine, GAME_TYPE_CONFIG
import os
import shutil
from datetime import datetime
from typing import List
import asyncio
import json

app = FastAPI(title="WinGo AI Prediction API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_prediction(self, prediction_data):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(prediction_data))
            except Exception as e:
                print(f"Error broadcasting to client: {e}")
                self.active_connections.remove(connection)

manager = ConnectionManager()
scheduler = None
ml_engine = MLEngine()

@app.on_event("startup")
def startup_event():
    init_db()
    global scheduler
    scheduler = PredictionScheduler(manager)
    scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    if scheduler:
        scheduler.shutdown()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Optionally handle client messages here
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/verify-request")
async def create_verify_request(
    tg_id: str = Form(...),
    uid: str = Form(...),
    screenshot: UploadFile = File(...)
):
    # Save screenshot
    uploads_dir = "uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    
    file_extension = screenshot.filename.split(".")[-1]
    filename = f"{tg_id}_{int(datetime.utcnow().timestamp())}.{file_extension}"
    file_path = os.path.join(uploads_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(screenshot.file, buffer)
    
    db = get_db()
    try:
        # Check if user exists
        user = db.query(User).filter(User.tg_id == tg_id).first()
        if not user:
            user = User(tg_id=tg_id, uid=uid, verified=False)
            db.add(user)
        else:
            user.uid = uid
        
        # Create verification request
        verify_request = VerifyRequest(
            tg_id=tg_id,
            uid_submitted=uid,
            screenshot_path=file_path,
            status="pending"
        )
        db.add(verify_request)
        db.commit()
        
        # Notify admin bot (this would be handled by the admin bot system)
        print(f"Verification request created for TG ID: {tg_id}")
        
        return {"message": "Verification request submitted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/admin/verify")
async def verify_request(request_id: int, action: str, admin_note: str = ""):
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be approve or reject")
    
    db = get_db()
    try:
        verify_request = db.query(VerifyRequest).filter(VerifyRequest.id == request_id).first()
        if not verify_request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        verify_request.status = action
        verify_request.admin_note = admin_note
        
        if action == "approve":
            # Update user status
            user = db.query(User).filter(User.tg_id == verify_request.tg_id).first()
            if user:
                user.verified = True
                user.verified_at = datetime.utcnow()
        
        db.commit()
        
        # In a real implementation, this would notify the user bot
        print(f"Request {request_id} {action}d")
        
        return {"message": f"Request {action}d successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/user/status/{tg_id}")
async def get_user_status(tg_id: str):
    db = get_db()
    try:
        user = db.query(User).filter(User.tg_id == tg_id).first()
        if not user:
            return {"status": "not_registered"}
        
        return {
            "status": "verified" if user.verified else "not_verified",
            "verified": user.verified
        }
    finally:
        db.close()

@app.get("/predict/{game_type}")
async def get_latest_prediction(game_type: str):
    if game_type not in GAME_TYPE_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid game type. Use: 30sec, 1min, 3min, 5min")
    
    db = get_db()
    try:
        prediction = db.query(Prediction).filter(
            Prediction.game_type == game_type
        ).order_by(Prediction.created_at.desc()).first()
        
        if not prediction:
            return {"message": f"No {game_type} predictions available"}
        
        return {
            "game_type": prediction.game_type,
            "period": prediction.period,
            "color": prediction.color,
            "confidence": prediction.confidence,
            "safe": prediction.safe,
            "model": prediction.model,
            "timestamp": prediction.created_at.isoformat()
        }
    finally:
        db.close()

@app.get("/predict")  # Default endpoint returns all game types
async def get_all_predictions():
    db = get_db()
    try:
        predictions = {}
        for game_type in GAME_TYPE_CONFIG.keys():
            pred = db.query(Prediction).filter(
                Prediction.game_type == game_type
            ).order_by(Prediction.created_at.desc()).first()
            
            if pred:
                predictions[game_type] = {
                    "period": pred.period,
                    "color": pred.color,
                    "confidence": pred.confidence,
                    "safe": pred.safe,
                    "model": pred.model,
                    "timestamp": pred.created_at.isoformat()
                }
            else:
                predictions[game_type] = {"message": f"No {game_type} predictions available"}
        
        return predictions
    finally:
        db.close()

@app.get("/admin/predictions/{game_type}")
async def get_predictions_by_game(game_type: str, limit: int = 20):
    if game_type not in GAME_TYPE_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid game type")
    
    db = get_db()
    try:
        predictions = db.query(Prediction).filter(
            Prediction.game_type == game_type
        ).order_by(Prediction.created_at.desc()).limit(limit).all()
        
        return [
            {
                "game_type": p.game_type,
                "period": p.period,
                "color": p.color,
                "confidence": p.confidence,
                "safe": p.safe,
                "model": p.model,
                "timestamp": p.created_at.isoformat()
            }
            for p in predictions
        ]
    finally:
        db.close()

@app.get("/admin/predictions")
async def get_all_predictions_admin(limit: int = 10):
    db = get_db()
    try:
        predictions = db.query(Prediction).order_by(
            Prediction.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "game_type": p.game_type,
                "period": p.period,
                "color": p.color,
                "confidence": p.confidence,
                "safe": p.safe,
                "model": p.model,
                "timestamp": p.created_at.isoformat()
            }
            for p in predictions
        ]
    finally:
        db.close()

@app.get("/admin/users")
async def get_users():
    db = get_db()
    try:
        users = db.query(User).all()
        
        return [
            {
                "id": u.id,
                "tg_id": u.tg_id,
                "uid": u.uid,
                "verified": u.verified,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "verified_at": u.verified_at.isoformat() if u.verified_at else None
            }
            for u in users
        ]
    finally:
        db.close()

@app.get("/admin/verify-requests")
async def get_verify_requests():
    db = get_db()
    try:
        requests = db.query(VerifyRequest).order_by(
            VerifyRequest.created_at.desc()
        ).all()
        
        return [
            {
                "id": r.id,
                "tg_id": r.tg_id,
                "uid_submitted": r.uid_submitted,
                "screenshot_path": r.screenshot_path,
                "status": r.status,
                "admin_note": r.admin_note,
                "created_at": r.created_at.isoformat()
            }
            for r in requests
        ]
    finally:
        db.close()

# New endpoints for game-specific predictions
@app.get("/predict/30sec")
async def get_30sec_prediction():
    return await get_latest_prediction("30sec")

@app.get("/predict/1min")
async def get_1min_prediction():
    return await get_latest_prediction("1min")

@app.get("/predict/3min")
async def get_3min_prediction():
    return await get_latest_prediction("3min")

@app.get("/predict/5min")
async def get_5min_prediction():
    return await get_latest_prediction("5min")