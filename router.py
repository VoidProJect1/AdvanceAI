"""
router.py — Smart routing engine for Void AI · Void Cipher V2.1

Priority:
  1. Groq (primary for ALL text tasks)
  2. Mistral (auto-fallback on rate limit, or forced via /mode)
  3. Mistral with web search (for live/current info queries)
  4. Mistral Vision (images always)
  5. Mistral OCR (documents always)
  6. Groq Whisper (voice always)
"""
import logging
import memory
import groq_client
import mistral_client
from config import HEAVY_KEYWORDS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Void AI (Void Cipher V2.1), an advanced AI assistant.
You are highly intelligent, fast, and direct. You adapt your tone automatically:
- Casual and friendly for small talk
- Precise and technical for code/analysis
- Structured and clear for research/explanation
You always respond in the same language the user writes in.
Never mention token counts, model names, or internal routing in your replies.
Keep responses concise unless detail is explicitly needed."""

WEB_TRIGGERS = [
    "today", "right now", "current", "latest", "news", "price",
    "weather", "live", "now", "2024", "2025", "2026", "who won",
    "what happened", "recent", "update", "trending", "stock",
    "score", "match", "breaking",
]


def _needs_web(text):
    lower = text.lower()
    return any(w in lower for w in WEB_TRIGGERS)


# ── Main text reply ───────────────────────────────────────────────────────────

def reply(uid, user_text):
    """
    Route text message → best AI engine.
    Returns (reply_text, engine_label).
    """
    memory.add_message(uid, "user", user_text)
    memory.bump(uid, "messages")

    mode         = memory.get(uid, "mode", "auto")
    groq_model   = memory.get(uid, "groq_model",   "llama-3.3-70b")
    mistral_model= memory.get(uid, "mistral_model", "mistral-large")
    ctx          = memory.get_context(uid, SYSTEM_PROMPT)

    try:
        # ── Force Mistral ─────────────────────────────────────────────────────
        if mode == "mistral":
            if _needs_web(user_text):
                text = mistral_client.web_search_chat(ctx, mistral_model)
                engine = f"Mistral {mistral_model} + Web"
            else:
                text = mistral_client.chat(ctx, mistral_model)
                engine = f"Mistral {mistral_model}"
            memory.add_message(uid, "assistant", text)
            return text, engine

        # ── Groq first (auto or force groq) ──────────────────────────────────
        text, hit_limit = groq_client.chat(ctx, groq_model)

        if not hit_limit:
            memory.add_message(uid, "assistant", text)
            return text, f"Groq {groq_model}"

        # ── Groq hit limit → auto fallback to Mistral ─────────────────────────
        logger.info(f"[{uid}] Groq limit → falling back to Mistral")
        if _needs_web(user_text):
            text = mistral_client.web_search_chat(ctx, mistral_model)
            engine = f"Mistral {mistral_model} + Web ⚡fallback"
        else:
            text = mistral_client.chat(ctx, mistral_model)
            engine = f"Mistral {mistral_model} ⚡fallback"

        memory.add_message(uid, "assistant", text)
        return text, engine

    except Exception as e:
        logger.error(f"Router error [{uid}]: {e}")
        raise


# ── Voice ─────────────────────────────────────────────────────────────────────

def voice_reply(uid, audio_path):
    """Transcribe (Groq Whisper) → reply. Returns (transcription, reply, engine)."""
    lang = memory.get(uid, "language", "auto")
    transcription, _ = groq_client.transcribe(audio_path, language=lang)
    memory.bump(uid, "voice")
    if not transcription.strip():
        return "", "Could not understand the audio.", "Whisper"
    text, engine = reply(uid, transcription)
    return transcription, text, engine


# ── Image ─────────────────────────────────────────────────────────────────────

def image_reply(uid, image_path, caption=None):
    """Vision analysis via Mistral Pixtral."""
    prompt = caption or "Describe this image in full detail."
    memory.bump(uid, "images")
    ctx    = memory.get_context(uid, SYSTEM_PROMPT)
    text   = mistral_client.analyze_image(image_path, prompt, ctx)
    memory.add_message(uid, "user",      f"[Image] {prompt}")
    memory.add_message(uid, "assistant", text)
    return text


# ── Document ──────────────────────────────────────────────────────────────────

def doc_reply(uid, file_path, question=None):
    """OCR → Groq summary. Returns (extracted, reply, engine)."""
    extracted = mistral_client.ocr_file(file_path)
    if not extracted.strip():
        return "", "Could not extract text from this document.", "OCR"

    prompt = (
        f"Document:\n\n{extracted[:6000]}\n\n---\nQuestion: {question}"
        if question
        else f"Summarize this document clearly:\n\n{extracted[:6000]}"
    )
    ctx   = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    groq_model = memory.get(uid, "groq_model", "llama-3.3-70b")
    text, hit  = groq_client.chat(ctx, groq_model)

    if hit:
        mistral_model = memory.get(uid, "mistral_model", "mistral-large")
        text = mistral_client.chat(ctx, mistral_model)
        engine = f"Mistral {mistral_model} ⚡fallback"
    else:
        engine = f"Groq {groq_model}"

    memory.add_message(uid, "user",      f"[Document] {question or 'Summarize'}")
    memory.add_message(uid, "assistant", text)
    return extracted, text, engine


# ── Web search only ───────────────────────────────────────────────────────────

def web_reply(uid, user_text):
    """Force a web-search-powered reply via Mistral."""
    memory.add_message(uid, "user", user_text)
    memory.bump(uid, "messages")
    mistral_model = memory.get(uid, "mistral_model", "mistral-large")
    ctx  = memory.get_context(uid, SYSTEM_PROMPT)
    text = mistral_client.web_search_chat(ctx, mistral_model)
    memory.add_message(uid, "assistant", text)
    return text, f"Mistral {mistral_model} + Web"
