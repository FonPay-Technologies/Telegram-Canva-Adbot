from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests, os

BOT_TOKEN = os.environ['BOT_TOKEN']
SERVER_URL = 'https://yourserver.com'  # where /create_token and /ad_callback live
ADS_PAGE = 'https://ads.yourdomain.com/watch.html'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Use /watch to watch an ad and get reward.")

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Create token (call server endpoint)
    r = requests.post(SERVER_URL + '/create_token', json={'user_id': str(user_id)})
    token = r.json().get('token')
    # Build URL with callback, user_id, token (URL-encode in production)
    callback = SERVER_URL + '/ad_callback'
    url = f"{ADS_PAGE}?user_id={user_id}&token={token}&callback={callback}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton('Watch Ad', url=url)]])
    await update.message.reply_text("Click below to watch an ad and earn your reward:", reply_markup=kb)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('watch', watch))
    app.run_polling()
