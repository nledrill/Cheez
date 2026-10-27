import asyncio, os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (Message, LabeledPrice, PreCheckoutQuery,
                           InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo)

TOKEN = os.environ["BOT_TOKEN"]
APP_URL = "https://nledrill.github.io/Cheez/"

bot = Bot(TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    arg = command.args or ""
    if arg.startswith("donate"):
        try:
            n = int(arg[6:])
        except ValueError:
            n = 50
        n = max(1, min(n, 10000))
        await bot.send_invoice(
            chat_id=m.chat.id,
            title="Донат cheez",
            description="Спасибо за поддержку! Игровой баланс не меняется.",
            payload=f"donate{n}",
            currency="XTR",
            prices=[LabeledPrice(label="Донат", amount=n)],
            provider_token="",
        )
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🧀 Играть", web_app=WebAppInfo(url=APP_URL))
    ]])
    await m.answer("Добро пожаловать в cheez! Звёзды в игре игровые.", reply_markup=kb)


@dp.message(F.text == "/links")
async def links(m: Message):
    out = []
    for n in (50, 100, 500):
        url = await bot.create_invoice_link(
            title="Донат cheez",
            description="Спасибо за поддержку! Игровой баланс не меняется.",
            payload=f"donate{n}",
            currency="XTR",
            prices=[LabeledPrice(label="Донат", amount=n)],
            provider_token="",
        )
        out.append(f"{n}: {url}")
    await m.answer("\n".join(out))


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@dp.message(F.successful_payment)
async def paid(m: Message):
    await m.answer("Спасибо за донат! ⭐🧀")


async def main():
    await dp.start_polling(bot)

asyncio.run(main())
