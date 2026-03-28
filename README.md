# 🤖 Advanced Telegram AI Bot

Powered by **Groq** (heavy tasks + Whisper STT) + **Mistral AI** (chat + vision + OCR + TTS)

---

## 📁 Files

```
ai_bot/
├── bot.py            ← Run this: python bot.py
├── router.py         ← Smart Groq/Mistral routing engine
├── groq_client.py    ← Groq API (LLM 70B/8B + Whisper STT)
├── mistral_client.py ← Mistral API (chat, vision, OCR, TTS)
├── personas.py       ← 8 AI personas
├── memory.py         ← Per-user chat history + settings
├── config.py         ← Configuration loader
├── requirements.txt
├── .env              ← Your API keys (create from .env.example)
└── data/             ← Auto-created (user data)
```

---

## ⚡ Setup

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Create .env
```bash
cp .env.example .env
# Edit .env and add your keys
```

### 3. Run
```bash
python bot.py
```

---

## 🔑 Get API Keys

| Key | Where |
|-----|-------|
| BOT_TOKEN | @BotFather on Telegram |
| GROQ_API_KEY | https://console.groq.com |
| MISTRAL_API_KEY | https://console.mistral.ai |
| ADMIN_IDS | @userinfobot on Telegram |

---

## ✨ Features

### 💬 Smart Chat Routing
- Short/normal messages → **Mistral Large**
- Code, analysis, long text → **Groq 70B**
- Force a specific engine with /mode

### 🎤 Voice Messages (Groq Whisper)
- Send voice note → auto-transcribed → AI replies
- Supports 50+ languages with auto-detection

### 🖼 Image Analysis (Mistral Vision)
- Send any photo → detailed description
- Add caption to ask specific questions

### 📄 Document OCR (Mistral OCR)
- Send PDF or image → text extracted → summarized
- Ask questions about document content via caption

### 🔊 Text to Speech (Mistral TTS)
- Toggle with /voicereply
- AI responses sent as voice audio

### 🧠 8 AI Personas
- Atlas (default), CodeX (coding), Sage (research)
- Quill (writing), Mentor (teaching), Lingo (translation)
- MedAssist (health info), Chef AI (cooking)

### ⚙️ Per-User Settings
- Persona, mode, language, voice reply — all saved per user
- Full conversation history with memory

---

## 🚀 Oracle VM Deployment

```bash
# Install Python 3.10+
sudo apt update && sudo apt install python3.10 python3-pip -y

# Install dependencies
pip3 install -r requirements.txt

# Run with screen
screen -S aibot
python3 bot.py
# Ctrl+A then D to detach
```

**systemd service:**
```bash
sudo nano /etc/systemd/system/aibot.service
```
```ini
[Unit]
Description=Telegram AI Bot
After=network.target

[Service]
WorkingDirectory=/home/opc/ai_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable aibot
sudo systemctl start aibot
```
