import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
)
from database import Database
from meme_utils import create_meme
from dotenv import load_dotenv
import requests

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Initialize database with bot instance
db = Database(bot=Bot(token=BOT_TOKEN))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎉 Welcome to GroupPal! I'm your group manager and meme buddy. Use /help for commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
    🛡️ GroupPal Commands:
    ⚙️ Moderation:
    /filter <word> <reply> - Add a word filter with auto-reply
    /filters - List or remove filters
    /quote - Quote a replied message

    🎭 Fun:
    /kang - Add a sticker to your collection (reply to sticker)
    /stickerpack - Show your sticker collection
    /mmf <text> - Create a meme from replied image/sticker/GIF

    🧑‍💻 Admin:
    /logs - View recent moderation logs (admin only)
    /getchatid - Get the chat ID for logging
    """
    await update.message.reply_text(help_text)

# Moderation: Filter words
async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /filter <word> <reply>")
        return
    trigger = context.args[0]
    reply = " ".join(context.args[1:])
    db.add_filter(trigger, reply)
    await update.message.reply_text(f"✅ Filter added: '{trigger}' -> '{reply}'")
    await db.log_action(update.message.from_user.id, f"Added filter: {trigger}")

async def list_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    filters = db.get_filters()
    if not filters:
        await update.message.reply_text("No filters set.")
        return
    filter_list = "\n".join([f"• {f[0]} -> {f[1]}" for f in filters])
    await update.message.reply_text(f"📋 Filters:\n{filter_list}")

async def remove_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /filters remove <word>")
        return
    trigger = context.args[1]
    db.remove_filter(trigger)
    await update.message.reply_text(f"🗑️ Filter '{trigger}' removed.")
    await db.log_action(update.message.from_user.id, f"Removed filter: {trigger}")

# Moderation: Quote message
async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a message to quote it.")
        return
    msg = update.message.reply_to_message
    author = msg.from_user.username or msg.from_user.first_name
    timestamp = msg.date.strftime("%Y-%m-%d %H:%M:%S")
    text = msg.text or msg.caption or "No text"
    quote_text = f"📌 [Quote from @{author} at {timestamp}]\n“{text}”"
    await update.message.reply_text(quote_text)
    await db.log_action(update.message.from_user.id, f"Quoted message ID: {msg.message_id}")

# Entertainment: Kang sticker
async def kang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.sticker:
        await update.message.reply_text("Reply to a sticker to kang it.")
        return
    sticker = update.message.reply_to_message.sticker
    user_id = update.message.from_user.id
    db.add_sticker(user_id, sticker.file_id)
    await update.message.reply_text("🐸 Kangged! Added to your sticker collection.")
    await db.log_action(user_id, "Kangged a sticker")

# Entertainment: Show sticker pack
async def stickerpack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    stickers = db.get_stickers(user_id)
    if not stickers:
        await update.message.reply_text("Your sticker collection is empty.")
        return
    keyboard = [[InlineKeyboardButton(f"Sticker {i+1}", callback_data=f"sticker_{s}")] for i, s in enumerate(stickers)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎨 Your sticker collection:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sticker_id = query.data.split("_")[1]
    await query.message.reply_sticker(sticker_id)

# Entertainment: Create meme
async def mmf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not update.message.reply_to_message:
        await update.message.reply_text("Usage: /mmf <text> (reply to image/sticker/GIF)")
        return
    text = " ".join(context.args)
    reply_msg = update.message.reply_to_message
    if reply_msg.photo:
        file_id = reply_msg.photo[-1].file_id
    elif reply_msg.sticker:
        file_id = reply_msg.sticker.file_id
    elif reply_msg.animation:
        file_id = reply_msg.animation.file_id
    else:
        await update.message.reply_text("Reply to an image, sticker, or GIF.")
        return
    file = await context.bot.get_file(file_id)
    meme_path = create_meme(file.file_path, text)
    await update.message.reply_sticker(open(meme_path, "rb"))
    await db.log_action(update.message.from_user.id, f"Created meme with text: {text}")

# Anti-spam: Rate limiting
user_message_count = {}
async def anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_message_count:
        user_message_count[user_id] = {"count": 0, "last_time": 0}
    from datetime import datetime
    current_time = datetime.now().timestamp()
    if current_time - user_message_count[user_id]["last_time"] < 60:
        user_message_count[user_id]["count"] += 1
        if user_message_count[user_id]["count"] > 5:  # 5 messages per minute
            await update.message.reply_text("🚫 Slow down! You're sending messages too fast.")
            return
    else:
        user_message_count[user_id] = {"count": 1, "last_time": current_time}

# Admin: View logs
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("🔐 Admin only command.")
        return
    logs = db.get_logs()
    log_text = "\n".join([f"[{l[1]}] User {l[0]}: {l[2]}" for l in logs])
    await update.message.reply_text(f"📋 Recent logs:\n{log_text}")

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_admins = await context.bot.get_chat_administrators(update.message.chat_id)
    return any(admin.user.id == user_id for admin in chat_admins)

# Get chat ID for logging
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Chat ID: {update.message.chat_id}")

# Filter message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        filters = db.get_filters()
        for trigger, reply in filters:
            if trigger.lower() in update.message.text.lower():
                await update.message.reply_text(reply)
                await db.log_action(update.message.from_user.id, f"Triggered filter: {trigger}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("filter", add_filter))
    app.add_handler(CommandHandler("filters", list_filters))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("kang", kang))
    app.add_handler(CommandHandler("stickerpack", stickerpack))
    app.add_handler(CommandHandler("mmf", mmf))
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(CommandHandler("getchatid", get_chat_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Sticker.ALL | filters.PHOTO | filters.ANIMATION, anti_spam))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Graceful shutdown
    try:
        app.run_polling()
    finally:
        db.close()  # Close database connection on shutdown

if __name__ == "__main__":
    main()
