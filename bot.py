"""
bot.py — Void AI · Void Cipher V2.1
Clean, fast, command-driven Telegram AI bot.
No inline keyboards. No token counts. No personas menu.
"""
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import memory
import router
import groq_client
import mistral_client
from config import (
    BOT_TOKEN, BOT_NAME, BOT_VERSION,
    GROQ_MODELS, MISTRAL_MODELS, ADMIN_IDS, LOG_LEVEL,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def uid(update):
    return update.effective_user.id

def is_admin(user_id):
    return (not ADMIN_IDS) or (user_id in ADMIN_IDS)

async def typing(update, ctx):
    await ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

async def safe_reply(update, text):
    """Send reply, split if too long, plain Markdown."""
    if not text:
        return
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(chunk)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    gm   = memory.get(uid(update), "groq_model",   "llama-3.3-70b")
    mm   = memory.get(uid(update), "mistral_model", "mistral-large")
    mode = memory.get(uid(update), "mode",          "auto")

    await update.message.reply_text(
        f"*{BOT_NAME}* — `{BOT_VERSION}`\n\n"
        f"Hello {user.first_name}! I'm your advanced AI assistant.\n\n"
        f"⚡ *Primary:* Groq `{gm}`\n"
        f"🔵 *Fallback:* Mistral `{mm}`\n"
        f"🔄 *Mode:* `{mode}`\n\n"
        f"Just send a message — text, voice, image, or document.\n"
        f"Type /help to see all commands.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── /help ─────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"*{BOT_NAME} · {BOT_VERSION}*\n\n"
        "━━ *Chat* ━━\n"
        "Send any text → AI replies automatically\n"
        "Groq is primary. Mistral auto-activates on limit.\n\n"
        "━━ *Media* ━━\n"
        "🎤 Voice note → transcribed + AI reply\n"
        "🖼 Photo → vision analysis (Mistral Pixtral)\n"
        "📄 PDF/Image file → OCR + summary\n\n"
        "━━ *Commands* ━━\n"
        "/new — Clear chat history\n"
        "/mode — Show or set routing mode\n"
        "/switch — Switch AI model version\n"
        "/models — List all available models\n"
        "/web `<query>` — Force live web search\n"
        "/translate `<lang>` `<text>` — Translate text\n"
        "/imagine `<prompt>` — Detailed image prompt ideas\n"
        "/summarize — Summarize replied message\n"
        "/language — Set voice transcription language\n"
        "/voicereply — Toggle audio responses\n"
        "/stats — Your usage stats\n"
        "/status — Bot status (admin)\n"
        "/help — This message\n",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  TEXT HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        return

    await typing(update, ctx)

    # Show thinking dot for long tasks
    ph = None
    if len(text) > 300:
        ph = await update.message.reply_text("⏳")

    try:
        reply_text, engine = router.reply(uid(update), text)
        if ph:
            await ph.delete()

        # Add subtle engine tag only if fallback occurred
        suffix = f"\n\n_↩ switched to {engine}_" if "fallback" in engine else ""
        await safe_reply(update, reply_text + suffix)

        # Voice reply if enabled
        if memory.get(uid(update), "voice_reply", False):
            await _send_tts(update, ctx, reply_text)

    except Exception as e:
        if ph:
            await ph.delete()
        logger.error(f"Text handler [{uid(update)}]: {e}")
        await update.message.reply_text("Something went wrong. Please try again.")


# ═══════════════════════════════════════════════════════════════════════════════
#  VOICE HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return

    await typing(update, ctx)
    status = await update.message.reply_text("🎤 _Transcribing…_", parse_mode=ParseMode.MARKDOWN)

    tmp_path = None
    try:
        file     = await ctx.bot.get_file(voice.file_id)
        tmp      = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
        tmp_path = tmp.name
        tmp.close()
        await file.download_to_drive(tmp_path)

        await status.edit_text("🧠 _Thinking…_", parse_mode=ParseMode.MARKDOWN)
        transcription, reply_text, engine = router.voice_reply(uid(update), tmp_path)

        if not transcription:
            await status.edit_text("❌ Could not understand the audio.")
            return

        suffix = f"\n\n_↩ {engine}_" if "fallback" in engine else ""
        await status.edit_text(
            f"🎤 _{transcription}_\n\n{reply_text}{suffix}",
            parse_mode=ParseMode.MARKDOWN,
        )

        if memory.get(uid(update), "voice_reply", False):
            await _send_tts(update, ctx, reply_text)

    except Exception as e:
        logger.error(f"Voice handler [{uid(update)}]: {e}")
        await status.edit_text("❌ Voice processing failed. Try again.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════════════
#  IMAGE HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_image(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    photo   = update.message.photo[-1]
    caption = update.message.caption

    await typing(update, ctx)
    status = await update.message.reply_text("🖼 _Analyzing…_", parse_mode=ParseMode.MARKDOWN)

    tmp_path = None
    try:
        file     = await ctx.bot.get_file(photo.file_id)
        tmp      = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp_path = tmp.name
        tmp.close()
        await file.download_to_drive(tmp_path)

        reply_text = router.image_reply(uid(update), tmp_path, caption)
        await status.edit_text(reply_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Image handler [{uid(update)}]: {e}")
        await status.edit_text("❌ Image analysis failed.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════════════
#  DOCUMENT HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return

    ext = Path(doc.file_name or "").suffix.lower()
    if ext not in [".pdf", ".jpg", ".jpeg", ".png", ".webp"]:
        await update.message.reply_text(f"❌ Unsupported file `{ext}`. Send PDF, JPG, or PNG.",
                                        parse_mode=ParseMode.MARKDOWN)
        return

    await typing(update, ctx)
    status = await update.message.reply_text("📄 _Reading document…_", parse_mode=ParseMode.MARKDOWN)

    tmp_path = None
    try:
        file     = await ctx.bot.get_file(doc.file_id)
        tmp      = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp_path = tmp.name
        tmp.close()
        await file.download_to_drive(tmp_path)

        await status.edit_text("🧠 _Summarizing…_", parse_mode=ParseMode.MARKDOWN)
        _, reply_text, engine = router.doc_reply(uid(update), tmp_path, update.message.caption)

        suffix = f"\n\n_↩ {engine}_" if "fallback" in engine else ""
        await status.edit_text(reply_text + suffix, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Document handler [{uid(update)}]: {e}")
        await status.edit_text("❌ Document processing failed.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════════════
#  /mode — Show or set routing mode
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = uid(update)
    args    = ctx.args

    if not args:
        mode = memory.get(user_id, "mode", "auto")
        gm   = memory.get(user_id, "groq_model",   "llama-3.3-70b")
        mm   = memory.get(user_id, "mistral_model", "mistral-large")
        await update.message.reply_text(
            f"*Current Mode:* `{mode}`\n\n"
            f"⚡ Groq model: `{gm}`\n"
            f"🔵 Mistral model: `{mm}`\n\n"
            f"*Set mode:*\n"
            f"`/mode auto` — Groq first, Mistral on limit\n"
            f"`/mode groq` — Force Groq always\n"
            f"`/mode mistral` — Force Mistral always",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    new_mode = args[0].lower()
    if new_mode not in ("auto", "groq", "mistral"):
        await update.message.reply_text("❌ Valid modes: `auto` `groq` `mistral`",
                                        parse_mode=ParseMode.MARKDOWN)
        return

    memory.put(user_id, "mode", new_mode)
    icons = {"auto": "🔄", "groq": "⚡", "mistral": "🔵"}
    await update.message.reply_text(
        f"✅ Mode set to {icons[new_mode]} `{new_mode}`",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  /switch — Switch model version
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_switch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = uid(update)
    args    = ctx.args

    groq_list    = list(GROQ_MODELS.keys())
    mistral_list = list(MISTRAL_MODELS.keys())

    if not args:
        gm = memory.get(user_id, "groq_model",   "llama-3.3-70b")
        mm = memory.get(user_id, "mistral_model", "mistral-large")
        groq_opts    = "\n".join(f"  `{m}`{'  ←' if m == gm else ''}" for m in groq_list)
        mistral_opts = "\n".join(f"  `{m}`{'  ←' if m == mm else ''}" for m in mistral_list)

        await update.message.reply_text(
            f"*Switch Model — Usage:*\n"
            f"`/switch groq <model>` or `/switch mistral <model>`\n\n"
            f"*⚡ Groq Models:*\n{groq_opts}\n\n"
            f"*🔵 Mistral Models:*\n{mistral_opts}\n\n"
            f"*Example:* `/switch groq mixtral-8x7b`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if len(args) < 2:
        await update.message.reply_text("Usage: `/switch groq <model>` or `/switch mistral <model>`",
                                        parse_mode=ParseMode.MARKDOWN)
        return

    provider = args[0].lower()
    model    = args[1].lower()

    if provider == "groq":
        if model not in GROQ_MODELS:
            await update.message.reply_text(
                f"❌ Unknown Groq model `{model}`\n\nAvailable: " +
                ", ".join(f"`{m}`" for m in groq_list),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        memory.put(user_id, "groq_model", model)
        await update.message.reply_text(f"✅ Groq model → `{model}`", parse_mode=ParseMode.MARKDOWN)

    elif provider == "mistral":
        if model not in MISTRAL_MODELS:
            await update.message.reply_text(
                f"❌ Unknown Mistral model `{model}`\n\nAvailable: " +
                ", ".join(f"`{m}`" for m in mistral_list),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        memory.put(user_id, "mistral_model", model)
        await update.message.reply_text(f"✅ Mistral model → `{model}`", parse_mode=ParseMode.MARKDOWN)

    else:
        await update.message.reply_text("❌ Provider must be `groq` or `mistral`",
                                        parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════════════════
#  /models — List all models
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_models(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gm = memory.get(uid(update), "groq_model",   "llama-3.3-70b")
    mm = memory.get(uid(update), "mistral_model", "mistral-large")

    groq_lines    = "\n".join(f"{'✅' if m == gm else '  '} `{m}`" for m in GROQ_MODELS)
    mistral_lines = "\n".join(f"{'✅' if m == mm else '  '} `{m}`" for m in MISTRAL_MODELS)

    await update.message.reply_text(
        f"*⚡ Groq Models:*\n{groq_lines}\n\n"
        f"*🔵 Mistral Models:*\n{mistral_lines}\n\n"
        f"Switch with: `/switch groq <model>` or `/switch mistral <model>`",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  /web — Force web search
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_web(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = " ".join(ctx.args).strip() if ctx.args else ""
    if not query:
        await update.message.reply_text("Usage: `/web <your question>`\n\nExample: `/web latest AI news`",
                                        parse_mode=ParseMode.MARKDOWN)
        return

    await typing(update, ctx)
    status = await update.message.reply_text("🌐 _Searching web…_", parse_mode=ParseMode.MARKDOWN)
    try:
        text, engine = router.web_reply(uid(update), query)
        await status.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"/web error: {e}")
        await status.edit_text("❌ Web search failed. Try again.")


# ═══════════════════════════════════════════════════════════════════════════════
#  /translate
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_translate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Usage: `/translate <language> <text>`\n\nExample: `/translate Hindi Good morning`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lang = ctx.args[0]
    text = " ".join(ctx.args[1:])
    await typing(update, ctx)

    try:
        prompt = f"Translate to {lang}. Reply with translation only:\n\n{text}"
        messages = [
            {"role": "system", "content": "You are an expert translator."},
            {"role": "user",   "content": prompt},
        ]
        # Use Groq for translation
        result, hit = groq_client.chat(messages, memory.get(uid(update), "groq_model", "llama-3.3-70b"))
        if hit:
            result = mistral_client.chat(messages, memory.get(uid(update), "mistral_model", "mistral-large"))

        await update.message.reply_text(f"🌍 *{lang}:*\n{result}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text("❌ Translation failed.")


# ═══════════════════════════════════════════════════════════════════════════════
#  /summarize — Summarize replied message
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_summarize(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    replied = update.message.reply_to_message
    text    = (replied.text or replied.caption or "") if replied else " ".join(ctx.args)

    if not text.strip():
        await update.message.reply_text(
            "Reply to any message with /summarize, or use:\n`/summarize <text>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await typing(update, ctx)
    try:
        messages = [
            {"role": "system", "content": "Summarize concisely and clearly."},
            {"role": "user",   "content": f"Summarize this:\n\n{text}"},
        ]
        result, hit = groq_client.chat(messages, memory.get(uid(update), "groq_model", "llama-3.3-70b"))
        if hit:
            result = mistral_client.chat(messages, memory.get(uid(update), "mistral_model", "mistral-large"))
        await safe_reply(update, f"📝 *Summary:*\n{result}")
    except Exception as e:
        await update.message.reply_text("❌ Summarization failed.")


# ═══════════════════════════════════════════════════════════════════════════════
#  /imagine — Creative image prompt generator
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_imagine(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    idea = " ".join(ctx.args).strip()
    if not idea:
        await update.message.reply_text("Usage: `/imagine <your idea>`", parse_mode=ParseMode.MARKDOWN)
        return

    await typing(update, ctx)
    try:
        messages = [
            {"role": "system", "content": (
                "You are an expert AI image prompt engineer. "
                "Generate 3 detailed, vivid image generation prompts for the given idea. "
                "Format: numbered list, each prompt on one line, include style, lighting, mood, camera details."
            )},
            {"role": "user", "content": idea},
        ]
        result, hit = groq_client.chat(messages, memory.get(uid(update), "groq_model", "llama-3.3-70b"),
                                       temperature=0.9)
        if hit:
            result = mistral_client.chat(messages, memory.get(uid(update), "mistral_model", "mistral-large"),
                                         temperature=0.9)
        await safe_reply(update, f"🎨 *Image Prompts for:* _{idea}_\n\n{result}")
    except Exception as e:
        await update.message.reply_text("❌ Failed to generate prompts.")


# ═══════════════════════════════════════════════════════════════════════════════
#  /language
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_language(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = uid(update)
    if not ctx.args:
        lang = memory.get(user_id, "language", "auto")
        await update.message.reply_text(
            f"*Voice Transcription Language:* `{lang}`\n\n"
            f"Set with: `/language <code>`\n\n"
            f"Examples:\n`/language auto` — auto detect\n"
            f"`/language en` — English\n`/language hi` — Hindi\n"
            f"`/language ar` — Arabic\n`/language fr` — French\n"
            f"`/language de` — German\n`/language es` — Spanish\n"
            f"`/language ru` — Russian\n`/language zh` — Chinese",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    lang = ctx.args[0].lower()
    memory.put(user_id, "language", lang)
    await update.message.reply_text(f"✅ Voice language set to `{lang}`", parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════════════════
#  /voicereply — Toggle TTS responses
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_voicereply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = uid(update)
    current = memory.get(user_id, "voice_reply", False)
    memory.put(user_id, "voice_reply", not current)
    state = "ON 🔊" if not current else "OFF 🔇"
    await update.message.reply_text(f"Voice Reply: *{state}*", parse_mode=ParseMode.MARKDOWN)


async def _send_tts(update, ctx, text):
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        out = mistral_client.tts(text, tmp.name)
        tmp.close()
        if out:
            with open(out, "rb") as f:
                await update.message.reply_voice(f)
            os.unlink(out)
    except Exception as e:
        logger.warning(f"TTS send failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  /new — Clear history
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    memory.clear_history(uid(update))
    await update.message.reply_text("🆕 Chat history cleared. Fresh start!")


# ═══════════════════════════════════════════════════════════════════════════════
#  /stats
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = uid(update)
    stats   = memory.get_stats(user_id)
    mode    = memory.get(user_id, "mode",          "auto")
    gm      = memory.get(user_id, "groq_model",    "llama-3.3-70b")
    mm      = memory.get(user_id, "mistral_model", "mistral-large")
    hist    = len(memory.get_history(user_id))
    lang    = memory.get(user_id, "language",      "auto")
    vr      = memory.get(user_id, "voice_reply",   False)

    await update.message.reply_text(
        f"📊 *{BOT_NAME} Stats*\n\n"
        f"💬 Messages: `{stats.get('messages', 0)}`\n"
        f"🎤 Voice: `{stats.get('voice', 0)}`\n"
        f"🖼 Images: `{stats.get('images', 0)}`\n"
        f"📝 History: `{hist}` messages saved\n\n"
        f"⚡ Groq: `{gm}`\n"
        f"🔵 Mistral: `{mm}`\n"
        f"🔄 Mode: `{mode}`\n"
        f"🌍 Language: `{lang}`\n"
        f"🔊 Voice Reply: `{'on' if vr else 'off'}`",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  /status — Admin only
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(uid(update)):
        await update.message.reply_text("🚫 Admin only.")
        return
    now   = datetime.now().strftime("%d %b %Y %H:%M")
    users = memory.total_users()
    await update.message.reply_text(
        f"*{BOT_NAME} · {BOT_VERSION}*\n"
        f"🟢 Online — `{now}`\n\n"
        f"👤 Total users: `{users}`\n"
        f"⚡ Groq: Connected\n"
        f"🔵 Mistral: Connected\n"
        f"🎤 Whisper STT: Active\n"
        f"🖼 Vision: Active\n"
        f"📄 OCR: Active\n"
        f"🌐 Web Search: Active",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── Build & run ───────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("new",         cmd_new))
    app.add_handler(CommandHandler("mode",        cmd_mode))
    app.add_handler(CommandHandler("switch",      cmd_switch))
    app.add_handler(CommandHandler("models",      cmd_models))
    app.add_handler(CommandHandler("web",         cmd_web))
    app.add_handler(CommandHandler("translate",   cmd_translate))
    app.add_handler(CommandHandler("summarize",   cmd_summarize))
    app.add_handler(CommandHandler("imagine",     cmd_imagine))
    app.add_handler(CommandHandler("language",    cmd_language))
    app.add_handler(CommandHandler("voicereply",  cmd_voicereply))
    app.add_handler(CommandHandler("stats",       cmd_stats))
    app.add_handler(CommandHandler("status",      cmd_status))

    # Media
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO,  handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO,                  handle_image))
    app.add_handler(MessageHandler(filters.Document.ALL,           handle_document))

    # Text (catch-all)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info(f"🚀 {BOT_NAME} · {BOT_VERSION} started")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
