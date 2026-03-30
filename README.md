# Scraper Bot

A powerful, stealth, multi-platform intelligence scraper.
Command it from WhatsApp, Telegram, or Terminal.
Results delivered as XLSX files.

---

## What it does

- Scrapes **any website**, Google, Facebook, Instagram, TikTok, LinkedIn, Twitter/X, Reddit, YouTube, news sites, RSS feeds
- Finds **jobs** across LinkedIn, Indeed, Glassdoor, BrighterMonday, and more simultaneously
- Generates **leads** — company names, emails, phones, websites by industry
- Does **market research** — prices, trends, competitor data, news
- Mines **conversations** — what people are saying about a topic across platforms
- **Posts/comments** on social media using your own accounts
- **CAPTCHA solving** via 2captcha service
- Human mimicry — realistic mouse, typing, scrolling, random delays
- Proxy rotation — auto-retires dead proxies
- All output in styled **.xlsx** files
- Delivered back to you on **WhatsApp, Telegram, Email, Google Drive, or local disk**

---

## Project structure

```
scraper_bot/
├── bot.py                    # Main entry point
├── bot_engine.py             # Central coordinator
├── requirements.txt
├── core/
│   ├── browser.py            # Stealth Playwright engine
│   ├── fetcher.py            # Fast httpx + BeautifulSoup
│   ├── extractor.py          # Regex data extractor
│   ├── queue.py              # Async job queue
│   ├── proxy.py              # Proxy rotation
│   └── command_parser.py     # Natural language command parser
├── scrapers/
│   ├── google.py
│   ├── twitter.py
│   ├── facebook.py
│   ├── instagram.py
│   ├── linkedin.py
│   ├── tiktok.py
│   ├── reddit.py
│   ├── news.py
│   └── generic.py            # Any URL
├── intelligence/
│   └── __init__.py           # Jobs, leads, market, conversations
├── automation/
│   └── poster.py             # Post/comment with your accounts
├── output/
│   ├── xlsx_builder.py       # Styled XLSX builder
│   ├── delivery.py           # Email, Drive, local
│   └── files/                # Output files saved here
└── interfaces/
    ├── telegram_bot.py
    ├── whatsapp.py
    └── cli.py
```

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure the bot

Edit `bot.py` — fill in `CONFIG`:

```python
CONFIG = {
    "headless": True,
    "captcha_api_key": "YOUR_2CAPTCHA_KEY",   # https://2captcha.com
    "proxies": [
        "http://user:pass@ip:port",            # optional
    ],
    "credentials": {
        "twitter":   {"username": "...", "password": "..."},
        "facebook":  {"username": "...", "password": "..."},
        "instagram": {"username": "...", "password": "..."},
        "linkedin":  {"username": "...", "password": "..."},
        "youtube":   {"username": "...", "password": "..."},
    },
    "telegram_token": "YOUR_TELEGRAM_BOT_TOKEN",
}
```

Leave empty anything you don't need.

### 3. Run

**Terminal mode (simplest):**
```bash
python bot.py --mode cli
```

**Telegram mode:**
```bash
python bot.py --mode telegram
```

**All interfaces at once:**
```bash
python bot.py --mode all
```

---

## WhatsApp setup

WhatsApp uses WPPConnect — connects your actual number, no paid API needed.

### Step 1 — Install Node.js
Download from https://nodejs.org (LTS version)

### Step 2 — Start WPPConnect server
```bash
npx @wppconnect-team/wppconnect-server
```

### Step 3 — Scan QR code
Open the URL shown in terminal (usually http://localhost:21465)
Scan the QR code with WhatsApp on your phone

### Step 4 — Run the bot
```bash
python bot.py --mode all
```

Now text your own number commands and it will reply with XLSX files.

---

## Telegram setup

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`, follow prompts, copy the token
3. Paste token in `CONFIG["telegram_token"]` in `bot.py`
4. Run `python bot.py --mode telegram`
5. Open your bot in Telegram and send `/start`

---

## Command examples

These work from WhatsApp, Telegram, and Terminal:

```
scrape https://example.com
scrape linkedin for python developer jobs in Nairobi
deep scrape twitter for posts about Safaricom
find 100 fintech leads in Kenya
jobs data analyst Nairobi remote
market research on mobile money East Africa
search reddit for remote freelance work
search google for solar companies Kenya contact email
find emails for safaricom.co.ke
post on twitter: Hello world!
post on linkedin: Excited to share my new project
comment on facebook: Great article!
```

---

## Delivery setup (optional)

### Email
Add to `CONFIG`:
```python
"email": {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
    "username": "you@gmail.com",
    "password": "your_app_password",  # Gmail App Password
    "to": "you@gmail.com",
}
```

### Google Drive
1. Go to https://console.cloud.google.com
2. Create a project → Enable Google Drive API
3. Create Service Account → Download JSON credentials
4. Share your Drive folder with the service account email

Add to `CONFIG`:
```python
"google_drive": {
    "credentials_file": "credentials.json",
    "folder_id": "YOUR_FOLDER_ID",  # from Drive URL
}
```

---

## Free deployment on Oracle Cloud (Always Free)

Oracle gives you a free Ubuntu VM — always on, forever free.

### Step 1 — Sign up
Go to https://www.oracle.com/cloud/free/
Sign up (needs credit card for verification — NOT charged)
Select "Always Free" resources only

### Step 2 — Create VM
- Compute → Instances → Create Instance
- Shape: VM.Standard.A1.Flex (4 OCPUs, 24GB RAM — free)
- Image: Ubuntu 22.04
- Add your SSH key

### Step 3 — Install dependencies
```bash
ssh ubuntu@YOUR_VM_IP

sudo apt update && sudo apt install -y python3.11 python3-pip nodejs npm git
pip install -r requirements.txt
playwright install chromium
playwright install-deps
```

### Step 4 — Run as a service (stays running forever)
```bash
sudo nano /etc/systemd/system/scraperbot.service
```

Paste:
```ini
[Unit]
Description=Scraper Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/scraper_bot
ExecStart=/usr/bin/python3 bot.py --mode all
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable scraperbot
sudo systemctl start scraperbot
sudo systemctl status scraperbot
```

Bot runs 24/7 for free.

---

## Notes

- Output files saved to `output/files/`
- Logs printed to terminal (use `loguru` for file logging if needed)
- CAPTCHA solving costs ~$2 per 1000 CAPTCHAs (2captcha.com)
- Free proxies are unreliable — use paid proxies for serious scraping
- Instagram scraping works best with `instaloader` (`pip install instaloader`)
- For Google Drive delivery: `pip install google-api-python-client google-auth`
