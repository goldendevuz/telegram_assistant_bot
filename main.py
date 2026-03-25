import os
import time
import html
from datetime import datetime, time as dt_time
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import UserStatusOnline, UserStatusOffline
from telethon.sessions import StringSession
import asyncio

print("Telethon version:", __import__('telethon').__version__)

load_dotenv()

api_id = int(os.getenv("TG_API_ID") or 0)
api_hash = os.getenv("TG_API_HASH") or ""
phone = os.getenv("TG_PHONE") or ""

USER_ID = os.getenv("USER_ID")
USER_ID = int(USER_ID) if USER_ID and USER_ID.isdigit() else None

# Default away message fallback
DEFAULT_AWAY_MESSAGE = (
    "Hozir offline-man. Keyinroq javob beraman. ✅<br>"
    "Shoshilinsa: <a href='tel:+998903611904'>+998903611904</a><br>"
    " Reklama: <a href='https://t.me/SecondSaverBot'>@SecondSaverBot</a>"
)

# parse mode: plain | html
MODE = (os.getenv("TG_MODE", "html") or "html").strip().lower()
if MODE not in ("plain", "html"):
    MODE = "plain"

# Per-user cooldown (spamdan himoya)
REPLY_COOLDOWN_SECONDS = int(os.getenv("TG_REPLY_COOLDOWN", "600"))

client = TelegramClient(StringSession(), api_id, api_hash)

IS_ACTIVE = True
_last_replied_at: dict[int, float] = {}
_last_replied_lock = asyncio.Lock()  # Variant A

# -------------------------------
# Multi-schedule away messages
# -------------------------------
away_messages_schedule = [
    # PDP Junior darslari
    {
        "weekdays": [0, 2, 4],
        "start": "15:00",
        "end": "16:30",
        "message": """Hozir darsda bo‘lishim mumkin, shuning uchun tez javob bera olmasligim mumkin. 📚<br>
Shoshilinsa: <a href='tel:+998903611904'>+998903611904</a><br>
 Reklama: <a href='https://t.me/SecondSaverBot'>@SecondSaverBot</a>"""
    },
    # Fintechhub darslari
    {
        "weekdays": [1, 3, 5],
        "start": "15:00",
        "end": "17:00",
        "message": """Hozir darsda bo‘lishim mumkin, shuning uchun tez javob bera olmasligim mumkin. 📚<br>
Shoshilinsa: <a href='tel:+998903611904'>+998903611904</a><br>
 Reklama: <a href='https://t.me/SecondSaverBot'>@SecondSaverBot</a>"""
    },
    # Kunduzgi bo‘sh vaqtlarda offline
    {
        "weekdays": list(range(7)),
        "start": "08:00",
        "end": "15:00",
        "message": """Hozir offline-man. Keyinroq javob beraman. ✅<br>
Shoshilinsa: <a href='tel:+998903611904'>+998903611904</a><br>
 Reklama: <a href='https://t.me/SecondSaverBot'>@SecondSaverBot</a>"""
    },
    # Kechki bo‘sh vaqt
    {
        "weekdays": list(range(7)),
        "start": "17:00",
        "end": "22:00",
        "message": """Hozir offline-man. Keyinroq javob beraman. ✅<br>
Shoshilinsa: <a href='tel:+998903611904'>+998903611904</a><br>
 Reklama: <a href='https://t.me/SecondSaverBot'>@SecondSaverBot</a>"""
    },
    # Kechki dam: 22:00–08:00
    {
        "weekdays": list(range(7)),
        "start": "22:00",
        "end": "08:00",
        "message": """Hozir kechki dam, 08:00 gacha javob bera olmayman. 🌙<br>
Shoshilinsa: <a href='tel:+998903611904'>+998903611904</a><br>
 Reklama: <a href='https://t.me/SecondSaverBot'>@SecondSaverBot</a>"""
    },
]

# -------------------------------
# Helper functions
# -------------------------------
def _normalize_away_message(text: str | None) -> str:
    text = (text or "").strip()
    return text if text else DEFAULT_AWAY_MESSAGE

def _current_away_message() -> str:
    now = datetime.now()
    current_time = now.time()
    weekday = now.weekday()

    for slot in away_messages_schedule:
        if weekday not in slot.get("weekdays", list(range(7))):
            continue

        start_h, start_m = map(int, slot["start"].split(":"))
        end_h, end_m = map(int, slot["end"].split(":"))
        start = dt_time(start_h, start_m)
        end = dt_time(end_h, end_m)

        if start <= end:
            if start <= current_time < end:
                return slot["message"]
        else:  # overnight interval
            if current_time >= start or current_time < end:
                return slot["message"]

    return DEFAULT_AWAY_MESSAGE

async def is_online() -> bool:
    me = await client.get_me()
    user = await client.get_entity(me.id)
    status = getattr(user, "status", None)

    if isinstance(status, UserStatusOnline):
        return True
    if isinstance(status, UserStatusOffline):
        return False
    return False

async def _is_saved_messages(event: events.NewMessage.Event) -> bool:
    me = await client.get_me()
    return event.is_private and event.chat_id == me.id

async def _can_reply_now(sender_id: int) -> bool:  # Variant A
    now = time.time()
    async with _last_replied_lock:
        last = _last_replied_at.get(sender_id, 0)
        if now - last < REPLY_COOLDOWN_SECONDS:
            return False
        _last_replied_at[sender_id] = now
        return True

def build_reply_payload(text: str | None) -> tuple[str, str | None]:
    msg = _normalize_away_message(text)
    if MODE == "plain":
        return msg, None
    return msg, "html"

# -------------------------------
# Saved Messages admin panel
# -------------------------------
@client.on(events.NewMessage(outgoing=True))
async def handle_outgoing_message(event: events.NewMessage.Event):
    global IS_ACTIVE, MODE, DEFAULT_AWAY_MESSAGE

    if not await _is_saved_messages(event):
        return

    text = (event.raw_text or "").strip()

    if text == "dis":
        IS_ACTIVE = False
        await event.respond("✅ Auto-reply: DISABLED")
        return

    if text == "en":
        IS_ACTIVE = True
        await event.respond("✅ Auto-reply: ENABLED")
        return

    if text == "get":
        msg, pm = build_reply_payload(_current_away_message())
        await event.respond(msg, parse_mode=pm)
        return

    if text.startswith("set\n"):
        new_msg = text.replace("set\n", "", 1)
        DEFAULT_AWAY_MESSAGE = _normalize_away_message(new_msg)
        await event.respond(
            "✅ Away message updated:\n" + html.escape(DEFAULT_AWAY_MESSAGE),
            parse_mode="html"
        )
        return

    if text == "mode":
        await event.respond(
            f"Current mode: <b>{html.escape(MODE)}</b>\nModes: plain | html",
            parse_mode="html"
        )
        return

    if text == "set_plain":
        MODE = "plain"
        await event.respond("✅ Mode set to PLAIN")
        return

    if text == "set_html":
        MODE = "html"
        await event.respond("✅ Mode set to HTML", parse_mode="html")
        return

    if text == "help":
        await event.respond(
            "Buyruqlar:\n- en\n- dis\n- get\n- set\\n<matn>\n- mode\n- set_plain\n- set_html",
            parse_mode="html"
        )
        return

# -------------------------------
# Incoming messages handler
# -------------------------------
@client.on(events.NewMessage(incoming=True))
async def handle_incoming_message(event: events.NewMessage.Event):
    if not IS_ACTIVE:
        return
    await send_auto_offline_message(event)

async def send_auto_offline_message(event: events.NewMessage.Event):
    if not event.is_private:
        return
    if await _is_saved_messages(event):
        return
    if not (event.raw_text or "").strip() and not event.message.media:
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return

    online = await is_online()
    if online:
        return

    if not await _can_reply_now(event.sender_id):  # async lock bilan
        return

    msg, pm = build_reply_payload(_current_away_message())
    try:
        await event.reply(msg, parse_mode=pm)
    except Exception:
        try:
            await event.reply(html.escape(msg))
        except Exception:
            pass

# -------------------------------
# Main
# -------------------------------
async def main():
    await client.start(phone)
    print("🤖 Auto-reply bot ishlayapti")
    print(f"MODE={MODE} | IS_ACTIVE={IS_ACTIVE}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
