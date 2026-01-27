import os
import time
import html
import telethon
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import UserStatusOnline, UserStatusOffline

print(telethon.__version__)

load_dotenv()

api_id = int(os.getenv("TG_API_ID") or 0)
api_hash = os.getenv("TG_API_HASH") or ""
phone = os.getenv("TG_PHONE") or ""

# Optional: Saved Messages ichida boshqarish uchun (o'zingizning user id)
USER_ID = os.getenv("USER_ID")
USER_ID = int(USER_ID) if USER_ID and USER_ID.isdigit() else None

# Away message (bo'sh bo'lib qolsa xato chiqadi, shuning uchun fallback bor)
DEFAULT_AWAY_MESSAGE = "Hozir offline-man. Keyinroq javob beraman. ✅"
away_message = (os.getenv("TG_MESSAGE") or "").strip() or DEFAULT_AWAY_MESSAGE

# parse mode rejimi: plain | html
MODE = (os.getenv("TG_MODE", "plain") or "plain").strip().lower()
if MODE not in ("plain", "html"):
    MODE = "plain"

# Spam bo'lmasligi uchun: bir userga qayta javob berish oralig'i (sekund)
REPLY_COOLDOWN_SECONDS = int(os.getenv("TG_REPLY_COOLDOWN", "600"))  # 10 min default

client = TelegramClient("offline_auto_reply", api_id, api_hash)

IS_ACTIVE = True
_last_replied_at: dict[int, float] = {}  # sender_id -> unix time


def _normalize_away_message(text: str | None) -> str:
    text = (text or "").strip()
    return text if text else DEFAULT_AWAY_MESSAGE


async def is_online() -> bool:
    """
    Telethon self-status. Ba'zi holatlarda status noaniq bo'lishi mumkin,
    lekin UserStatusOnline/UserStatusOffline bo'yicha minimal check qilamiz.
    """
    me = await client.get_me()
    user = await client.get_entity(me.id)
    status = getattr(user, "status", None)
    print(status)

    if isinstance(status, UserStatusOnline):
        return True
    if isinstance(status, UserStatusOffline):
        return False

    # Status noma'lum bo'lsa: ehtiyotkorlik bilan offline deb qabul qilamiz
    return False


async def _is_saved_messages(event: events.NewMessage.Event) -> bool:
    """
    Saved Messages chat_id odatda o'zingizning user id'ingizga teng bo'ladi.
    """
    me = await client.get_me()
    return event.is_private and event.chat_id == me.id


def _can_reply_now(sender_id: int) -> bool:
    now = time.time()
    last = _last_replied_at.get(sender_id, 0)
    if now - last < REPLY_COOLDOWN_SECONDS:
        return False
    _last_replied_at[sender_id] = now
    return True


def build_reply_payload(text: str | None) -> tuple[str, str | None]:
    """
    Returns (message_text, parse_mode)
    MODE=plain  -> parse_mode None (no entity parsing)
    MODE=html   -> parse_mode "html" (Telegram HTML)
    """
    msg = _normalize_away_message(text)

    if MODE == "plain":
        return msg, None

    # MODE == "html"
    # NOTE: Bu yerda msg'ni escape QILMAYMIZ — haqiqiy HTML ishlashi uchun.
    # Agar siz taglar ishlamasin, faqat xavfsiz plain ko'rinishda ketsin desangiz:
    # return html.escape(msg), "html"
    return msg, "html"


@client.on(events.NewMessage(outgoing=True))
async def handle_outgoing_message(event: events.NewMessage.Event):
    """
    Saved Messages orqali boshqaruv:
      dis        -> disable
      en         -> enable
      get        -> show away message
      set\n<txt>  -> update away message

      mode       -> show current MODE
      set_plain  -> MODE=plain
      set_html   -> MODE=html
    """
    global IS_ACTIVE, away_message, MODE

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
        msg, pm = build_reply_payload(away_message)
        if pm:
            await event.respond(msg, parse_mode=pm)
        else:
            await event.respond(msg)
        return

    if text.startswith("set\n"):
        new_msg = text.replace("set\n", "", 1)
        away_message = _normalize_away_message(new_msg)

        # Tasdiqni har doim html bilan chiroyli ko'rsatamiz (xavfsiz)
        await event.respond(
            "✅ Away message updated:\n" + html.escape(away_message),
            parse_mode="html",
        )
        return

    if text == "mode":
        await event.respond(
            f"Current mode: <b>{html.escape(MODE)}</b>\nModes: plain | html",
            parse_mode="html",
        )
        return

    if text == "set_plain":
        MODE = "plain"
        await event.respond("✅ Mode set to PLAIN")
        return

    if text == "set_html":
        MODE = "html"
        await event.respond("✅ Mode set to HTML (Telegram HTML parse)", parse_mode="html")
        return

    await event.respond(
        "Buyruqlar:\n"
        "- en\n- dis\n- get\n- set\\n<matn>\n"
        "- mode\n- set_plain\n- set_html",
        parse_mode="html",
    )


@client.on(events.NewMessage(incoming=True))
async def handle_incoming_message(event: events.NewMessage.Event):
    if not IS_ACTIVE:
        print("Handler is disabled")
        return

    print("Handler is enabled")
    await send_auto_offline_message(event)


async def send_auto_offline_message(event: events.NewMessage.Event):
    # Faqat private chat
    if not event.is_private:
        return

    # O'zingizga / Saved Messages'ga javob bermasin
    if await _is_saved_messages(event):
        return

    # Service message yoki bo'sh kontent bo'lishi mumkin
    if not (event.raw_text or "").strip() and not event.message.media:
        return

    # Botlarga javob bermaslik
    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return

    online = await is_online()
    if online:
        print(f"[{event.sender_id}] dan xabar keldi, lekin siz ONLINE. Javob berilmadi.")
        return

    # Spamni kamaytirish
    if not _can_reply_now(event.sender_id):
        print(f"[{event.sender_id}] uchun cooldown. Javob yuborilmadi.")
        return

    msg, pm = build_reply_payload(away_message)

    try:
        if pm:
            await event.respond(msg, parse_mode=pm)
        else:
            await event.respond(msg)
        print(f"[{event.sender_id}] dan kelgan xabarga javob berildi.")
    except Exception as e:
        # HTML parse error bo'lsa, plain fallback
        print(f"Auto-reply error (MODE={MODE}): {e}. Falling back to plain.")
        try:
            await event.respond(html.escape(msg))  # plain (no parse_mode)
        except Exception as e2:
            print(f"Fallback ham xato: {e2}")


async def main():
    await client.start(phone)
    print("🤖 Avtomatik javob beruvchi ishga tushdi.")
    print(f"MODE={MODE} | COOLDOWN={REPLY_COOLDOWN_SECONDS}s | IS_ACTIVE={IS_ACTIVE}")
    await client.run_until_disconnected()


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
