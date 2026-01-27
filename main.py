from telethon import TelegramClient, events
from telethon.tl.types import UserStatusOnline, UserStatusOffline, Message
from dotenv import load_dotenv
import telethon
import os

print(telethon.__version__)

load_dotenv()

api_id = os.getenv("TG_API_ID")
api_hash = os.getenv("TG_API_HASH")
phone = os.getenv("TG_PHONE")
print(api_id, api_hash, phone)
away_message = os.getenv("TG_MESSAGE")
client = TelegramClient('offline_auto_reply', api_id, api_hash)

last_status = None

IS_ACTIVE = True

async def is_online():
    me = await client.get_me()
    user = await client.get_entity(me.id)
    print(user.status)
    if isinstance(user.status, UserStatusOnline):
        return True
    elif isinstance(user.status, UserStatusOffline):
        return False
    # else:
    #     return None


@client.on(events.NewMessage(outgoing=True))
async def handle_outgoing_message(event: Message):
    global IS_ACTIVE
    global away_message
    print(event.saved_peer_id)
    text = event.message.message
    if event.saved_peer_id.user_id == os.getenv("USER_ID"):
        print("Chat is Saved Messages", event.message)
        if text == "dis":
            print("Disabling")
            IS_ACTIVE = False
        elif text == "en":
            print("Enabling")
            IS_ACTIVE = True
        elif text.startswith("set\n"):
            away_message = text.replace("set\n", "", 1)
            await event.respond(f"Away message has been updated:\n{away_message}", parse_mode="html")
        elif text == "get":
            await event.respond(away_message, parse_mode="html")
    else:
        print("Chat is not Saved Messages")


@client.on(events.NewMessage(incoming=True))
async def handle_incoming_message(event: Message):
    global IS_ACTIVE
    if IS_ACTIVE:
        print("Handler is enabled")
    else:
        print("Handler is disabled")

    if IS_ACTIVE:
        await send_auto_offline_message(event)


async def send_auto_offline_message(event):
    if not event.is_private:
        return

    online = await is_online()

    if online:
        print(f"[{event.sender_id}] dan xabar keldi, lekin siz online bo‘lgansiz, javob berilmadi.")
        return

    try:
        await event.respond(away_message, parse_mode="html")
        print(f"[{event.sender_id}] dan kelgan xabarga javob berildi.")
    except Exception as e:
        print(f"Javob berishda xatolik yuz berdi: {e}")


async def main():
    await client.start(phone)
    print("🤖 Avtomatik javob beruvchi ishga tushdi.")
    await client.run_until_disconnected()


if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
