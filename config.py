"""
config.py — Void AI · Void Cipher V2.1
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Identity ──────────────────────────────────────────────────────────────────
BOT_NAME    = "Void AI"
BOT_VERSION = "Void Cipher V2.1"

# ── Telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing in .env")

_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()]

# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing in .env")
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY missing in .env")

# ── Groq Models ───────────────────────────────────────────────────────────────
GROQ_MODELS = {
    "llama-3.3-70b":   "llama-3.3-70b-versatile",
    "llama-3.1-70b":   "llama-3.1-70b-versatile",
    "llama-3.1-8b":    "llama-3.1-8b-instant",
    "llama-3-70b":     "llama3-70b-8192",
    "llama-3-8b":      "llama3-8b-8192",
    "mixtral-8x7b":    "mixtral-8x7b-32768",
    "gemma2-9b":       "gemma2-9b-it",
}
GROQ_DEFAULT_MODEL  = "llama-3.3-70b"
GROQ_WHISPER_MODEL  = "whisper-large-v3"

# ── Mistral Models ────────────────────────────────────────────────────────────
MISTRAL_MODELS = {
    "mistral-large":   "mistral-large-latest",
    "mistral-small":   "mistral-small-latest",
    "mistral-medium":  "mistral-medium-latest",
    "pixtral-large":   "pixtral-large-latest",
    "codestral":       "codestral-latest",
    "mistral-nemo":    "open-mistral-nemo",
}
MISTRAL_DEFAULT_MODEL  = "mistral-large"
MISTRAL_VISION_MODEL   = "pixtral-large-latest"
MISTRAL_OCR_MODEL      = "mistral-ocr-latest"

# ── Routing ───────────────────────────────────────────────────────────────────
# Groq is PRIMARY. Mistral is FALLBACK (rate limit) + media tasks
HEAVY_KEYWORDS = [
    "code", "program", "python", "javascript", "typescript", "debug", "error",
    "fix", "analyze", "analysis", "explain", "compare", "research", "summarize",
    "essay", "write a", "algorithm", "function", "class", "sql", "html", "css",
    "script", "build", "develop", "difference", "translate", "step by step",
]

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
DATA_DIR  = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_FILE   = DATA_DIR / "users.json"

# ── Limits ─────────────────────────────────────────────────────────────────────
MAX_HISTORY  = 24
MAX_TOKENS   = 2048
LOG_LEVEL    = os.getenv("LOG_LEVEL", "INFO")
