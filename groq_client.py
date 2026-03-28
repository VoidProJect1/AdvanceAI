"""
groq_client.py — Groq API (Primary AI Engine)
Void AI · Void Cipher V2.1
"""
import logging
import os
from groq import Groq, RateLimitError, APIStatusError
from config import GROQ_API_KEY, GROQ_MODELS, GROQ_WHISPER_MODEL, MAX_TOKENS

logger  = logging.getLogger(__name__)
_client = Groq(api_key=GROQ_API_KEY)


def chat(messages, model_key="llama-3.3-70b", temperature=0.7):
    """
    Send to Groq. Returns (text, hit_limit).
    hit_limit=True means caller should switch to Mistral.
    """
    model = GROQ_MODELS.get(model_key, GROQ_MODELS["llama-3.3-70b"])
    try:
        resp = _client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=MAX_TOKENS,
        )
        text = resp.choices[0].message.content
        logger.info(f"Groq [{model_key}] OK — {len(text)} chars")
        return text, False

    except RateLimitError:
        logger.warning(f"Groq rate limit hit on {model_key} — switching to Mistral")
        return None, True

    except APIStatusError as e:
        if e.status_code in (429, 503):
            logger.warning(f"Groq {e.status_code} — switching to Mistral")
            return None, True
        logger.error(f"Groq API error {e.status_code}: {e.message}")
        raise

    except Exception as e:
        logger.error(f"Groq unexpected error: {e}")
        raise


def transcribe(file_path, language=None):
    """Whisper STT — always uses Groq regardless of mode."""
    try:
        params = {
            "file":            (os.path.basename(file_path), open(file_path, "rb")),
            "model":           GROQ_WHISPER_MODEL,
            "response_format": "verbose_json",
        }
        if language and language != "auto":
            params["language"] = language

        result   = _client.audio.transcriptions.create(**params)
        text     = result.text.strip()
        detected = getattr(result, "language", "?")
        logger.info(f"Whisper: '{text[:60]}' (lang: {detected})")
        return text, detected

    except Exception as e:
        logger.error(f"Whisper error: {e}")
        raise


def list_models():
    return list(GROQ_MODELS.keys())
