import os, shutil, asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base, InBodyMeasurement, User
from .parser import parse_inbody_pdf
from .auth import router as auth_router, get_current_user, require_admin
from .bot import bot_manager

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запуск бота при старте (если в базе есть токен)
    asyncio.create_task(bot_manager.run())
    yield
    # Остановка бота при завершении
    await bot_manager.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="frontend"), name="static")
app.include_router(auth_router, prefix="/auth", tags=["auth"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload/")
async def upload_pdf(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        data = parse_inbody_pdf(file_path)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга: {e}")
    os.remove(file_path)

    db = SessionLocal()
    try:
        existing = db.query(InBodyMeasurement).filter_by(date=data["date"], user_id=current_user.id).first()
        if existing:
            db.delete(existing)
            db.commit()
        data["user_id"] = current_user.id
        measurement = InBodyMeasurement(**data)
        db.add(measurement)
        db.commit()
        return {"message": f"Данные за {data['date']} сохранены", "data": data}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения в БД: {e}")
    finally:
        db.close()

@app.get("/measurements/")
def get_measurements(current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        rows = db.query(InBodyMeasurement).filter_by(user_id=current_user.id).order_by(InBodyMeasurement.date).all()
        result = []
        for row in rows:
            item = {}
            for col in row.__table__.columns:
                item[col.name] = getattr(row, col.name)
            result.append(item)
        return result
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def root():
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/login.html", response_class=HTMLResponse)
def login_page():
    with open("frontend/login.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/register.html", response_class=HTMLResponse)
def register_page():
    with open("frontend/register.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/settings.html", response_class=HTMLResponse)
def settings_page():
    with open("frontend/settings.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin.html", response_class=HTMLResponse)
def admin_page():
    with open("frontend/admin.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/upload-test/")
async def upload_test(file: UploadFile = File(...)):
    return {"filename": file.filename, "size": len(await file.read())}

@app.get("/upload-test.html", response_class=HTMLResponse)
def test_upload_page():
    with open("frontend/test-upload.html", "r", encoding="utf-8") as f:
        return f.read()
