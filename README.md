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
TG_CONTACT_PHONE=
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

---

## 👤 Author & License

Created by **Abdulmajid Yunus** ([@goldendevuz](https://github.com/goldendevuz)).

Licensed under the MIT License with Attribution. See [LICENSE](LICENSE).
Forks and derivative works must keep the author attribution above in their README.

---

## 🖥 Admin panel

A responsive web panel (`static/index.html`) for the auto-reply settings and per-user rules:

- Turn auto-reply on/off, choose HTML/plain mode, edit the default message
- Per-user messages (by Telegram user ID), optionally limited to a time window (e.g. `09:00`–`18:00`)
- Protected with HTTP Basic auth (`ADMIN_USER` / `ADMIN_PASSWORD` in `.env`); disabled if the password is empty

Settings and rules are stored in SQLite (`/app/data/bot.db` in Docker), so they survive restarts.

### Public access via Cloudflare Tunnel (server)

1. In the Cloudflare dashboard, add a public hostname to your tunnel, e.g. `tg.example.uz`, pointing to the service `http://telegram_assistant_bot:8000`.
2. Put the tunnel token in `.env.tunnel` on the server (never commit it):
   ```env
   TUNNEL_TOKEN=your-tunnel-token
   ```
3. Start everything, including the tunnel:
   ```bash
   docker compose --profile tunnel up -d --build
   ```

Local development does not start `cloudflared` (no profile), so it cannot take over the production tunnel.
