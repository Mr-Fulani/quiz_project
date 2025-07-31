# # quiz_project/mini_app/app_handlers/handlers.py

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from mini_app.config import WEBAPP_URL

router = Router(name="mini_app_router")



@router.message(Command("profile"))
async def handle_profile_command(message: types.Message):
    webapp_button = InlineKeyboardButton(
        text="Запустить приложение",
        web_app=WebAppInfo(url=f"{WEBAPP_URL}/")  # Уберем /profile/, так как у нас корневой маршрут
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[webapp_button]])
    
    await message.answer(
        "Нажмите кнопку ниже, чтобы открыть приложение:",
        reply_markup=keyboard
    )
