from aiogram.types import Update
from fastapi import FastAPI
from fastapi.requests import Request
from bot import lifespan, dp, bot
from shared.config import WEBHOOK_ENDPOINT

app = FastAPI(lifespan=lifespan)


@app.post(f"/{WEBHOOK_ENDPOINT}")
async def webhook(request: Request) -> None:
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
