import os
import random
import string
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from .database import SessionLocal, User, AppSettings, get_setting, set_setting

SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool = False
    telegram_id: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class AdminSettings(BaseModel):
    telegram_bot_token: str
    bot_username: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        if user_id is None:
            raise credentials_exception
    except (JWTError, ValueError, TypeError):
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user

# Временное хранилище кодов привязки
pending_links = {}

def link_telegram_by_code(code: str, telegram_id: str, db: Session) -> bool:
    for uid, c in pending_links.items():
        if c == code:
            user = db.query(User).filter(User.id == uid).first()
            if user:
                user.telegram_id = telegram_id
                db.commit()
                del pending_links[uid]
                return True
    return False

router = APIRouter()

@router.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter((User.username == user.username) | (User.email == user.email)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    # Первый пользователь становится администратором
    is_admin = db.query(User).count() == 0
    hashed = get_password_hash(user.password)
    new_user = User(username=user.username, email=user.email, hashed_password=hashed, is_admin=is_admin)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/bot-info")
def get_bot_info(db: Session = Depends(get_db)):
    username = get_setting(db, "bot_username", None)
    return {"username": username or ""}

@router.get("/telegram/link")
def get_telegram_link(current_user: User = Depends(get_current_user)):
    code = ''.join(random.choices(string.digits, k=6))
    pending_links[current_user.id] = code
    return {"code": code, "instruction": f"Отправьте боту команду /start {code}"}

@router.delete("/telegram")
def unlink_telegram(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.telegram_id = None
    db.commit()
    return {"message": "Telegram отвязан"}

# ---- Администраторские эндпоинты ----
@router.get("/admin/settings", response_model=AdminSettings)
def get_admin_settings(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    token = get_setting(db, "telegram_bot_token", "")
    username = get_setting(db, "bot_username", "")
    return {"telegram_bot_token": token, "bot_username": username}

@router.put("/admin/settings")
def update_admin_settings(settings: AdminSettings, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    set_setting(db, "telegram_bot_token", settings.telegram_bot_token)
    set_setting(db, "bot_username", settings.bot_username)
    # Здесь можно добавить перезапуск бота (через глобальный объект), но для простоты
    # потребуется ручной перезапуск сервиса или кнопка "Перезапустить бота".
    return {"message": "Settings saved. Restart the bot to apply changes."}

@router.post("/admin/restart-bot")
async def restart_bot(admin: User = Depends(require_admin)):
    from .bot import bot_manager
    await bot_manager.async_restart()
    return {"message": "Bot restart initiated."}
    # Будет реализовано в main.py через глобальный объект bot_manager
    from .main import bot_manager
    if bot_manager:
        bot_manager.restart()
        return {"message": "Bot restart initiated."}
    return {"message": "Bot manager not available."}
