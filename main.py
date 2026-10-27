import asyncio
import html
import logging
import os
import re
import time
from datetime import datetime, time as dt_time

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import UserStatusOnline

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("autoreply")

# .env dagi sozlamalar
API_ID = int(os.getenv("TG_API_ID") or 0)
API_HASH = os.getenv("TG_API_HASH") or ""
PHONE = os.getenv("TG_PHONE") or ""
SESSION = os.getenv("TG_SESSION") or "telegram_session"  # login ma'lumoti shu faylda saqlanadi
MODE = (os.getenv("TG_MODE") or "html").strip().lower()  # plain | html
REPLY_COOLDOWN_SECONDS = int(os.getenv("TG_REPLY_COOLDOWN") or 600)  # bir foydalanuvchiga javob oralig'i

if not API_ID or not API_HASH:
    raise SystemExit("TG_API_ID va TG_API_HASH .env faylida ko'rsatilishi shart")
if MODE not in ("plain", "html"):
    MODE = "plain"

# -------------------------------
# Away messages
# -------------------------------
CONTACT = (
    "Shoshilinsa: <a href='tel:+998903611904'>+998903611904</a>\n"
    "Reklama: <a href='https://t.me/SecondSaverBot'>@SecondSaverBot</a>"
)
OFFLINE_TEXT = "Hozir offline-man. Keyinroq javob beraman. ✅"
CLASS_MESSAGE = f"Hozir darsda bo‘lishim mumkin, shuning uchun tez javob bera olmasligim mumkin. 📚\n{CONTACT}"
NIGHT_MESSAGE = f"Hozir kechki dam, 08:00 gacha javob bera olmayman. 🌙\n{CONTACT}"

# /set buyrug'i bilan o'zgaradi. Jadvaldagi "message": None bo'lgan oraliqlar shuni ishlatadi.
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

IS_ACTIVE = False
ME_ID: int | None = None
_last_reply_at: dict[int, float] = {}

# -------------------------------
# Helpers
# -------------------------------
def _in_window(now: dt_time, start: dt_time, end: dt_time) -> bool:
    if start <= end:
        return start <= now < end
    return now >= start or now < end  # tun oralig'i, masalan 22:00–08:00

def current_away_message() -> str:
    now = datetime.now()
    for slot in AWAY_SCHEDULE:
        if now.weekday() in slot["weekdays"] and _in_window(now.time(), slot["start"], slot["end"]):
            return slot["message"] or DEFAULT_AWAY_MESSAGE
    return DEFAULT_AWAY_MESSAGE

def build_reply_payload(text: str) -> tuple[str, str | None]:
    if MODE == "plain":
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
    global IS_ACTIVE, MODE, DEFAULT_AWAY_MESSAGE

    text = (event.raw_text or "").strip()

    if text == "en":
        IS_ACTIVE = True
        await event.respond("✅ Auto-reply: ENABLED", parse_mode=None)
    elif text == "dis":
        IS_ACTIVE = False
        await event.respond("✅ Auto-reply: DISABLED", parse_mode=None)
    elif text == "get":
        msg, pm = build_reply_payload(current_away_message())
        await event.respond(msg, parse_mode=pm)
    elif text.startswith("set\n"):
        new_msg = text[len("set\n"):].strip()
        if not new_msg:
            await event.respond("❌ Matn bo'sh. Format: set + yangi matn keyingi qatorda", parse_mode=None)
            return
        DEFAULT_AWAY_MESSAGE = new_msg
        await event.respond(
            "✅ Away message updated:\n" + html.escape(DEFAULT_AWAY_MESSAGE),
            parse_mode="html",
        )
    elif text == "mode":
        await event.respond(
            f"Current mode: <b>{MODE}</b>\nModes: plain | html",
            parse_mode="html",
        )
    elif text == "set_plain":
        MODE = "plain"
        await event.respond("✅ Mode set to PLAIN", parse_mode=None)
    elif text == "set_html":
        MODE = "html"
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
    if not IS_ACTIVE:
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

    msg, pm = build_reply_payload(current_away_message())
    try:
        await event.reply(msg, parse_mode=pm)
    except Exception:
        log.exception("HTML bilan javob yuborilmadi, oddiy matn sifatida qayta urinilmoqda")
        await event.reply(_strip_html(msg), parse_mode=None)

# -------------------------------
# Main
# -------------------------------
async def main():
    global ME_ID

    phone = PHONE or (lambda: input("Telefon raqamingiz (+998...): "))
    await client.start(phone=phone)

    ME_ID = (await client.get_me()).id
    log.info("🤖 Auto-reply bot ishlayapti | MODE=%s | IS_ACTIVE=%s", MODE, IS_ACTIVE)
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("To'xtatildi")
