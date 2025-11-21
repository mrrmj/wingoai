from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(String, unique=True, index=True)
    uid = Column(String)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)

class VerifyRequest(Base):
    __tablename__ = 'verify_requests'
    
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(String, index=True)
    uid_submitted = Column(String)
    screenshot_path = Column(String)
    status = Column(String, default='pending')  # pending, approved, rejected
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Prediction(Base):
    __tablename__ = 'predictions'
    
    id = Column(Integer, primary_key=True, index=True)
    game_type = Column(String, index=True)  # '30sec', '1min', '3min', '5min'
    period = Column(String)
    color = Column(String)
    confidence = Column(Float)
    safe = Column(Boolean)
    model = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Setting(Base):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True)
    value = Column(Text)

class Log(Base):
    __tablename__ = 'logs'
    
    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text)
    level = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)