import asyncio
import html
import logging
import os
import re
import time
from datetime import datetime, time as dt_time
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import UserStatusOnline

import storage
import web

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("autoreply")

# .env dagi sozlamalar
API_ID = int(os.getenv("TG_API_ID") or 0)
API_HASH = os.getenv("TG_API_HASH") or ""
PHONE = os.getenv("TG_PHONE") or ""
SESSION = os.getenv("TG_SESSION") or "telegram_session"  # login ma'lumoti shu faylda saqlanadi
MODE = (os.getenv("TG_MODE") or "html").strip().lower()  # boshlang'ich qiymat, keyin DB dan olinadi
REPLY_COOLDOWN_SECONDS = int(os.getenv("TG_REPLY_COOLDOWN") or 600)  # bir foydalanuvchiga javob oralig'i
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or ""
ADMIN_HOST = os.getenv("ADMIN_HOST") or "0.0.0.0"
ADMIN_PORT = int(os.getenv("ADMIN_PORT") or 8000)

if not API_ID or not API_HASH:
    raise SystemExit("TG_API_ID va TG_API_HASH .env faylida ko'rsatilishi shart")
if MODE not in ("plain", "html"):
    MODE = "plain"

# -------------------------------
# Away messages
# -------------------------------
CONTACT_PHONE = os.getenv("TG_CONTACT_PHONE") or ""  # xabarda ko'rsatiladigan telefon (ixtiyoriy)
CONTACT = "\n".join(
    line for line in (
        f"Shoshilinsa: <a href='tel:{CONTACT_PHONE}'>{CONTACT_PHONE}</a>" if CONTACT_PHONE else "",
        "Reklama: <a href='https://t.me/SecondSaverBot'>@SecondSaverBot</a>",
    ) if line
)
OFFLINE_TEXT = "Hozir offline-man. Keyinroq javob beraman. ✅"
CLASS_MESSAGE = f"Hozir darsda bo‘lishim mumkin, shuning uchun tez javob bera olmasligim mumkin. 📚\n{CONTACT}"
NIGHT_MESSAGE = f"Hozir kechki dam, 08:00 gacha javob bera olmayman. 🌙\n{CONTACT}"

# Boshlang'ich standart xabar. Keyin admin panel yoki "set" buyrug'i DB'da o'zgartiradi.
DEFAULT_AWAY_MESSAGE = f"{OFFLINE_TEXT}\n{CONTACT}"

ALL_DAYS = range(7)  # 0 = Dushanba ... 6 = Yakshanba
AWAY_SCHEDULE = [
    # PDP Junior darslari: Du, Chor, Juma
    {"weekdays": (0, 2, 4), "start": dt_time(15, 0), "end": dt_time(16, 30), "message": CLASS_MESSAGE},
    # Fintechhub darslari: Se, Pay, Shan
    {"weekdays": (1, 3, 5), "start": dt_time(15, 0), "end": dt_time(17, 0), "message": CLASS_MESSAGE},
    # Kunduzgi bo'sh vaqt
    {"weekdays": ALL_DAYS, "start": dt_time(8, 0), "end": dt_time(15, 0), "message": None},
    # Kechki bo'sh vaqt
    {"weekdays": ALL_DAYS, "start": dt_time(17, 0), "end": dt_time(22, 0), "message": None},
    # Kechki dam: 22:00–08:00
    {"weekdays": ALL_DAYS, "start": dt_time(22, 0), "end": dt_time(8, 0), "message": NIGHT_MESSAGE},
]

# -------------------------------
# State
# -------------------------------
client = TelegramClient(SESSION, API_ID, API_HASH)

ME_ID: int | None = None
_last_reply_at: dict[int, float] = {}

HEARTBEAT_FILE = "/tmp/bot_heartbeat"
HEARTBEAT_INTERVAL_SECONDS = 60

# -------------------------------
# Helpers
# -------------------------------
def is_active() -> bool:
    return storage.get_settings().get("is_active") == "1"

def current_mode() -> str:
    return storage.get_settings().get("mode", MODE)

def default_message() -> str:
    return storage.get_settings().get("default_message", DEFAULT_AWAY_MESSAGE)

def _in_window(now: dt_time, start: dt_time, end: dt_time) -> bool:
    if start <= end:
        return start <= now < end
    return now >= start or now < end  # tun oralig'i, masalan 22:00–08:00

def current_away_message() -> str:
    now = datetime.now()
    for slot in AWAY_SCHEDULE:
        if now.weekday() in slot["weekdays"] and _in_window(now.time(), slot["start"], slot["end"]):
            return slot["message"] or default_message()
    return default_message()

def rule_message_now(user_id: int) -> str | None:
    """Foydalanuvchi uchun faol maxsus xabar. Yo'q bo'lsa None (standart jadval ishlaydi)."""
    rule = storage.get_rule(user_id)
    if not rule or not rule["enabled"]:
        return None
    if rule["start_time"] and rule["end_time"]:
        start = dt_time.fromisoformat(rule["start_time"])
        end = dt_time.fromisoformat(rule["end_time"])
        if not _in_window(datetime.now().time(), start, end):
            return None
    return rule["message"]

def build_reply_payload(text: str) -> tuple[str, str | None]:
    if current_mode() == "plain":
        return text, None
    return text, "html"

def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text))

def _can_reply_now(sender_id: int) -> bool:
    now = time.time()
    if now - _last_reply_at.get(sender_id, 0) < REPLY_COOLDOWN_SECONDS:
        return False
    _last_reply_at[sender_id] = now
    return True

async def is_online() -> bool:
    me = await client.get_me()
    return isinstance(me.status, UserStatusOnline)

def _is_saved_messages(event: events.NewMessage.Event) -> bool:
    return event.is_private and event.chat_id == ME_ID

# -------------------------------
# Saved Messages admin panel
# -------------------------------
@client.on(events.NewMessage(outgoing=True, func=_is_saved_messages))
async def handle_command(event: events.NewMessage.Event):
    text = (event.raw_text or "").strip()

    if text == "en":
        storage.set_setting("is_active", "1")
        await event.respond("✅ Auto-reply: ENABLED", parse_mode=None)
    elif text == "dis":
        storage.set_setting("is_active", "0")
        await event.respond("✅ Auto-reply: DISABLED", parse_mode=None)
    elif text == "get":
        msg, pm = build_reply_payload(current_away_message())
        await event.respond(msg, parse_mode=pm)
    elif text.startswith("set\n"):
        new_msg = text[len("set\n"):].strip()
        if not new_msg:
            await event.respond("❌ Matn bo'sh. Format: set + yangi matn keyingi qatorda", parse_mode=None)
            return
        storage.set_setting("default_message", new_msg)
        await event.respond(
            "✅ Away message updated:\n" + html.escape(new_msg),
            parse_mode="html",
        )
    elif text == "mode":
        await event.respond(
            f"Current mode: <b>{current_mode()}</b>\nModes: plain | html",
            parse_mode="html",
        )
    elif text == "set_plain":
        storage.set_setting("mode", "plain")
        await event.respond("✅ Mode set to PLAIN", parse_mode=None)
    elif text == "set_html":
        storage.set_setting("mode", "html")
        await event.respond("✅ Mode set to HTML", parse_mode="html")
    elif text == "help":
        await event.respond(
            "Buyruqlar:\n- en\n- dis\n- get\n- set (yangi matn keyingi qatorda)\n- mode\n- set_plain\n- set_html",
            parse_mode=None,
        )

# -------------------------------
# Incoming messages handler
# -------------------------------
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handle_incoming(event: events.NewMessage.Event):
    if not is_active():
        return
    if not (event.raw_text or "").strip() and not event.message.media:
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return

    if await is_online():
        return

    if not _can_reply_now(event.sender_id):
        return

    text = rule_message_now(event.sender_id) or current_away_message()
    msg, pm = build_reply_payload(text)
    try:
        await event.reply(msg, parse_mode=pm)
    except Exception:
        log.exception("HTML bilan javob yuborilmadi, oddiy matn sifatida qayta urinilmoqda")
        await event.reply(_strip_html(msg), parse_mode=None)

# -------------------------------
# Background tasks
# -------------------------------
async def heartbeat():
    # Docker healthcheck uchun: fayl vaqti yangilanib turadi
    while True:
        Path(HEARTBEAT_FILE).touch()
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

async def serve_admin():
    config = uvicorn.Config(web.app, host=ADMIN_HOST, port=ADMIN_PORT, log_level="warning", access_log=False)
    log.info("Admin panel: http://%s:%s", ADMIN_HOST, ADMIN_PORT)
    await uvicorn.Server(config).serve()

# -------------------------------
# Main
# -------------------------------
async def main():
    global ME_ID

    storage.init({"is_active": "0", "mode": MODE, "default_message": DEFAULT_AWAY_MESSAGE})
    asyncio.create_task(heartbeat())

    if ADMIN_PASSWORD:
        asyncio.create_task(serve_admin())
    else:
        log.warning("ADMIN_PASSWORD bo'sh: admin panel ishga tushmaydi")

    phone = PHONE or (lambda: input("Telefon raqamingiz (+998...): "))
    await client.start(phone=phone)

    ME_ID = (await client.get_me()).id
    log.info("🤖 Auto-reply bot ishlayapti | MODE=%s | IS_ACTIVE=%s", current_mode(), is_active())
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("To'xtatildi")
