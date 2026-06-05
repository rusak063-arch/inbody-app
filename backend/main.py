import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

# Импорты из наших модулей (теперь относительные)
from .database import SessionLocal, engine, Base, InBodyMeasurement
from .parser import parse_inbody_pdf

# Создаём таблицы (на случай первого запуска)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Монтируем папку frontend как статику (доступна по /static)
# Путь относительно корня проекта (где лежит frontend/)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Папка для временного хранения загруженных PDF (внутри backend)
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/upload/")
async def upload_pdf(file: UploadFile = File(...)):
    """Загрузить PDF, распарсить и сохранить в базу."""
    # Сохраняем временно
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        data = parse_inbody_pdf(file_path)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга: {e}")

    # Удаляем временный файл
    os.remove(file_path)

    # Сохраняем в БД (если на эту дату уже есть запись – обновляем)
    db = SessionLocal()
    try:
        existing = db.query(InBodyMeasurement).filter_by(date=data["date"]).first()
        if existing:
            db.delete(existing)
            db.commit()
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
def get_measurements():
    """Получить все измерения в хронологическом порядке."""
    db = SessionLocal()
    try:
        rows = db.query(InBodyMeasurement).order_by(InBodyMeasurement.date).all()
        # Преобразуем каждую строку в словарь, чтобы сериализовать JSON-поля
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
    """Главная страница с графиками."""
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return f.read()
