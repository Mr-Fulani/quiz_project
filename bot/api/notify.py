from aiogram import Bot
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel



router = APIRouter()



class MessagePayload(BaseModel):
    chat_id: int
    text: str
    parse_mode: str = "Markdown"



@router.post("/send-message/")
async def send_message(payload: MessagePayload, bot: Bot):
    """
    Отправляет сообщение в Telegram от имени бота.
    """
    try:
        await bot.send_message(chat_id=payload.chat_id, text=payload.text, parse_mode=payload.parse_mode)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))