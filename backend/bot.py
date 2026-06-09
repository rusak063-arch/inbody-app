import os
import asyncio
import tempfile
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram import Router
from sqlalchemy.orm import Session

from .database import SessionLocal, get_setting, User, InBodyMeasurement
from .parser import parse_inbody_pdf
from .auth import link_telegram_by_code

class BotManager:
    def __init__(self):
        self.bot = None
        self.dp = None
        self._task = None

    def get_token(self):
        db = SessionLocal()
        token = get_setting(db, "telegram_bot_token", None)
        db.close()
        return token

    async def run(self):
        token = self.get_token()
        if not token:
            print("TELEGRAM_BOT_TOKEN not set in database. Bot disabled.")
            return
        # Если уже есть запущенный бот, останавливаем его
        if self._task and not self._task.done():
            await self.stop()
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        router = Router()

        @router.message(Command("start"))
        async def cmd_start(message: Message):
            args = message.text.split()
            if len(args) == 2:
                code = args[1]
                telegram_id = str(message.from_user.id)
                db = SessionLocal()
                success = link_telegram_by_code(code, telegram_id, db)
                db.close()
                if success:
                    await message.answer("✅ Ваш Telegram привязан к аккаунту InBody. Теперь отправляйте PDF-файлы.")
                else:
                    await message.answer("❌ Неверный код привязки. Проверьте и попробуйте снова.")
            else:
                await message.answer(
                    "Привет! Я бот InBody Tracker.\n"
                    "Используйте /start <код> для привязки аккаунта.\n"
                    "После привязки отправляйте PDF-отчёты."
                )

        @router.message(F.document)
        async def handle_pdf(message: Message):
            telegram_id = str(message.from_user.id)
            db = SessionLocal()
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                await message.answer("❌ Ваш Telegram не привязан к аккаунту. Сначала привяжитесь через веб-интерфейс.")
                db.close()
                return

            document = message.document
            if not document.file_name or not document.file_name.lower().endswith('.pdf'):
                await message.answer("❌ Пожалуйста, отправьте файл в формате PDF.")
                db.close()
                return

            try:
                file_id = document.file_id
                file = await self.bot.get_file(file_id)
                tmp_path = tempfile.mktemp(suffix=".pdf")
                await self.bot.download_file(file.file_path, tmp_path)

                data = parse_inbody_pdf(tmp_path)

                existing = db.query(InBodyMeasurement).filter_by(date=data["date"], user_id=user.id).first()
                if existing:
                    db.delete(existing)
                    db.commit()

                data["user_id"] = user.id
                measurement = InBodyMeasurement(**data)
                db.add(measurement)
                db.commit()

                summary = (
                    f"📊 Данные сохранены!\n"
                    f"Дата: {data['date']}\n"
                    f"Вес: {data['weight_kg']} кг\n"
                    f"Мышцы: {data['muscle_kg']} кг\n"
                    f"Жир: {data['fat_percent']}%\n"
                    f"Висцеральный жир: {data['visceral_fat_level']} уровень\n"
                    f"ИМТ: {data['bmi']}\n"
                    f"Основной обмен: {data['bmr_kcal']} ккал"
                )
                await message.answer(summary)
            except Exception as e:
                await message.answer(f"❌ Ошибка при обработке PDF: {str(e)}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                db.close()

        self.dp.include_router(router)
        self._task = asyncio.create_task(self.dp.start_polling(self.bot))

    async def stop(self):
        """Немедленно отменить поллинг, не дожидаясь завершения."""
        if self._task and not self._task.done():
            self._task.cancel()
            # Не ждём завершения задачи – это предотвращает зависание
        if self.bot:
            await self.bot.session.close()
            self.bot = None
        self._task = None

    async def async_restart(self):
        await self.stop()
        await self.run()

bot_manager = BotManager()
