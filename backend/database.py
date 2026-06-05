from sqlalchemy import create_engine, Column, Date, Float, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///inbody_progress.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class InBodyMeasurement(Base):
    __tablename__ = "inbody_measurements"

    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False)
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
    # JSON поля: списки из 5 значений (правая рука, левая рука, туловище, правая нога, левая нога)
    segmental_muscle_kg = Column(JSON)
    segmental_muscle_pct = Column(JSON)
    segmental_fat_kg = Column(JSON)
    segmental_fat_pct = Column(JSON)

# Создать таблицы, если их ещё нет
Base.metadata.create_all(bind=engine)