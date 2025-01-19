# # quiz_project/mini_app/app_handlers/handlers.py

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup

router = Router(name="mini_app_router")

WEBAPP_URL = "https://f098-185-241-101-35.ngrok-free.app"  # Обновите на текущий URL

@router.message(Command("profile"))
async def handle_profile_command(message: types.Message):
    webapp_button = InlineKeyboardButton(
        text="Открыть профиль",
        web_app=WebAppInfo(url=f"{WEBAPP_URL}/")  # Уберем /profile/, так как у нас корневой маршрут
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[webapp_button]])
    
    await message.answer(
        "Нажмите кнопку ниже, чтобы открыть приложение:",
        reply_markup=keyboard
    )
