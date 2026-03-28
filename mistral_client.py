"""
mistral_client.py — Mistral AI (Fallback + Media + Web Search)
Void AI · Void Cipher V2.1
"""
import base64
import logging
import os
import tempfile
from pathlib import Path
from mistralai import Mistral
from config import (
    MISTRAL_API_KEY, MISTRAL_MODELS, MISTRAL_VISION_MODEL,
    MISTRAL_OCR_MODEL, MAX_TOKENS
)

logger  = logging.getLogger(__name__)
_client = Mistral(api_key=MISTRAL_API_KEY)


# ── Chat (fallback) ───────────────────────────────────────────────────────────

def chat(messages, model_key="mistral-large", temperature=0.7):
    """Mistral chat — used as Groq fallback or when forced."""
    model = MISTRAL_MODELS.get(model_key, MISTRAL_MODELS["mistral-large"])
    try:
        resp  = _client.chat.complete(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=MAX_TOKENS,
        )
        text  = resp.choices[0].message.content
        logger.info(f"Mistral [{model_key}] OK — {len(text)} chars")
        return text

    except Exception as e:
        logger.error(f"Mistral chat error: {e}")
        raise


# ── Web Search (live info) ─────────────────────────────────────────────────────

def web_search_chat(messages, model_key="mistral-large"):
    """
    Mistral chat WITH web search tool enabled.
    Use this for: current events, live prices, news, today's date queries.
    """
    model = MISTRAL_MODELS.get(model_key, MISTRAL_MODELS["mistral-large"])
    try:
        resp = _client.chat.complete(
            model=model,
            messages=messages,
            max_tokens=MAX_TOKENS,
            tools=[{"type": "web_search"}],
            tool_choice="auto",
        )
        text = resp.choices[0].message.content
        logger.info(f"Mistral WebSearch [{model_key}] OK")
        return text

    except Exception as e:
        # Fallback: normal chat without web search
        logger.warning(f"Web search failed, falling back to normal: {e}")
        return chat(messages, model_key)


# ── Vision ────────────────────────────────────────────────────────────────────

def analyze_image(image_path, prompt="Describe this image in detail.", ctx=None):
    """Pixtral vision — analyze any image."""
    try:
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()

        ext  = Path(image_path).suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png",  "webp": "image/webp"}.get(ext, "image/jpeg")

        messages = []
        if ctx:
            messages += [m for m in ctx if m["role"] == "system"]
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": f"data:{mime};base64,{data}"},
                {"type": "text",      "text": prompt},
            ]
        })

        resp = _client.chat.complete(model=MISTRAL_VISION_MODEL, messages=messages,
                                     max_tokens=MAX_TOKENS)
        return resp.choices[0].message.content

    except Exception as e:
        logger.error(f"Mistral vision error: {e}")
        raise


# ── OCR ───────────────────────────────────────────────────────────────────────

def ocr_file(file_path):
    """Extract text from PDF or image using Mistral OCR."""
    try:
        ext = Path(file_path).suffix.lower()
        with open(file_path, "rb") as f:
            raw = base64.b64encode(f.read()).decode()

        if ext == ".pdf":
            doc = {"type": "document_url",
                   "document_url": f"data:application/pdf;base64,{raw}"}
        else:
            mime = {".png": "image/png", ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/jpeg")
            doc  = {"type": "image_url", "image_url": f"data:{mime};base64,{raw}"}

        result = _client.ocr.process(model=MISTRAL_OCR_MODEL, document=doc,
                                     include_image_base64=False)
        pages  = getattr(result, "pages", [])
        text   = "\n\n".join(p.markdown for p in pages if hasattr(p, "markdown"))
        return text or str(result)

    except Exception as e:
        logger.error(f"Mistral OCR error: {e}")
        raise


# ── TTS ───────────────────────────────────────────────────────────────────────

def tts(text, out_path):
    """Text to speech — returns audio file path or None on failure."""
    try:
        resp = _client.audio.speech.create(
            model="mistral-tts-latest",
            voice="fr-woman-1",
            input=text[:900],
        )
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return out_path
    except Exception as e:
        logger.warning(f"TTS unavailable: {e}")
        return None


def list_models():
    return list(MISTRAL_MODELS.keys())
