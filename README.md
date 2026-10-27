# Telegram Offline Auto Reply Bot (Telethon)

This project is a **Telegram userbot** built with **Telethon** that automatically sends a reply
**when you are offline**.

The bot:
- Does **NOT reply** when you are online
- Automatically replies when you are offline
- Works only in **private chats**
- Can be fully controlled via **Saved Messages**

---

## 🚀 Features

- 🔄 Detects Telegram online/offline status
- 🤖 Sends automatic replies when offline
- 🔐 Controlled only from **Saved Messages**
- 🛑 Enable / disable auto-reply anytime
- ✏️ Update auto-reply message dynamically

---

## 🛠 Requirements

- Python **3.10+**
- Telegram account
- `api_id` and `api_hash` from https://my.telegram.org
- Telethon library

---

## 📦 Installation

### Create virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

---

## 🐳 Docker

### Configure

Create a `.env` file next to `docker-compose.yml`:

```env
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
TG_PHONE=
TG_MODE=html
TG_REPLY_COOLDOWN=600
```

### First login (once)

Telegram asks for your phone number and the login code, so start the container interactively:

```bash
docker compose run --rm telegram_assistant_bot
```

After login, the session is stored in the `telethon_session` volume. Stop with `Ctrl+C`.

### Run in background

```bash
docker compose up -d --build
docker compose logs -f telegram_assistant_bot
```

### Update

```bash
git pull
docker compose up -d --build
```
