import asyncio, hashlib, hmac, json, os, time
from urllib.parse import parse_qsl

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (Message, LabeledPrice, PreCheckoutQuery,
                           InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo)

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_LOGIN = os.environ.get("ADMIN_LOGIN", "")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "")
DATA_DIR = os.environ.get("DATA_DIR", ".")
APP_URL = "https://nledrill.github.io/Cheez/"
DB_PATH = os.path.join(DATA_DIR, "promos.json")

bot = Bot(TOKEN)
dp = Dispatcher()
lock = asyncio.Lock()


# ---------- база промокодов (файл JSON) ----------
def load():
    try:
        with open(DB_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"promos": {}, "used": {}}


def save(db):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False)
    os.replace(tmp, DB_PATH)


def clean(c):
    return "".join(ch for ch in str(c).upper().strip() if ch.isalnum() or ch in "_-")


def tg_user(init_data):
    """Проверяет подпись Telegram и возвращает id пользователя."""
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        h = pairs.pop("hash")
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, h):
            return None
        if time.time() - int(pairs.get("auth_date", "0")) > 86400:
            return None
        return json.loads(pairs["user"])["id"]
    except Exception:
        return None


def admin_ok(d):
    if not ADMIN_LOGIN or not ADMIN_PASS:
        return False
    a = hmac.compare_digest(str(d.get("login", "")).encode(), ADMIN_LOGIN.encode())
    b = hmac.compare_digest(str(d.get("password", "")).encode(), ADMIN_PASS.encode())
    return a and b


async def body(request):
    try:
        return json.loads(await request.text())
    except Exception:
        return {}


def err(msg):
    return web.json_response({"ok": False, "error": msg})


# ---------- HTTP API для мини-приложения ----------
@web.middleware
async def cors(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response()
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as e:
            resp = e
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    return resp


async def health(request):
    return web.Response(text="ok")


async def redeem(request):
    d = await body(request)
    uid = tg_user(d.get("initData", ""))
    if uid is None:
        return err("Откройте приложение из Telegram")
    c = clean(d.get("code", ""))
    async with lock:
        db = load()
        p = db["promos"].get(c)
        if not p or p["left"] <= 0:
            return err("Промокод не найден или закончился")
        if uid in db["used"].get(c, []):
            return err("Вы уже активировали этот код")
        p["left"] -= 1
        db["used"].setdefault(c, []).append(uid)
        save(db)
    return web.json_response({"ok": True, "stars": p["stars"]})


async def a_login(request):
    d = await body(request)
    return web.json_response({"ok": True}) if admin_ok(d) else err("Неверный логин или пароль")


async def a_list(request):
    d = await body(request)
    if not admin_ok(d):
        return err("Нет доступа")
    return web.json_response({"ok": True, "promos": load()["promos"]})


async def a_create(request):
    d = await body(request)
    if not admin_ok(d):
        return err("Нет доступа")
    c = clean(d.get("code", ""))
    try:
        stars, mx = int(d.get("stars")), int(d.get("max"))
    except Exception:
        return err("Неверные числа")
    if not c or not (1 <= stars <= 10**12) or not (1 <= mx <= 10**9):
        return err("Неверные данные")
    async with lock:
        db = load()
        db["promos"][c] = {"stars": stars, "max": mx, "left": mx}
        db["used"].pop(c, None)
        save(db)
    return web.json_response({"ok": True})


async def a_delete(request):
    d = await body(request)
    if not admin_ok(d):
        return err("Нет доступа")
    c = clean(d.get("code", ""))
    async with lock:
        db = load()
        db["promos"].pop(c, None)
        db["used"].pop(c, None)
        save(db)
    return web.json_response({"ok": True})


# ---------- бот ----------
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
    app = web.Application(middlewares=[cors])
    app.router.add_get("/", health)
    app.router.add_post("/redeem", redeem)
    app.router.add_post("/admin/login", a_login)
    app.router.add_post("/admin/list", a_list)
    app.router.add_post("/admin/create", a_create)
    app.router.add_post("/admin/delete", a_delete)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", "8080"))).start()
    await dp.start_polling(bot)


asyncio.run(main())
