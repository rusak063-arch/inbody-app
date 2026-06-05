from sqlalchemy import create_engine, Column, Date, Float, Integer, String, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os

DATABASE_URL = "sqlite:///inbody_progress.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    measurements = relationship("InBodyMeasurement", back_populates="owner")

class InBodyMeasurement(Base):
    __tablename__ = "inbody_measurements"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    weight_kg = Column(Float)
    muscle_kg = Column(Float)
    fat_percent = Column(Float)
    visceral_fat_level = Column(Integer)
    bmi = Column(Float)
    ffm_kg = Column(Float)
    bmr_kcal = Column(Integer)
    daily_calories = Column(Integer)
    water_l = Column(Float)
    protein_kg = Column(Float)
    bone_kg = Column(Float)
    optimal_weight_kg = Column(Float)
    segmental_muscle_kg = Column(JSON)
    segmental_muscle_pct = Column(JSON)
    segmental_fat_kg = Column(JSON)
    segmental_fat_pct = Column(JSON)
    owner = relationship("User", back_populates="measurements")

Base.metadata.create_all(bind=engine)
