import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import gspread
from google.oauth2.service_account import Credentials

# Configuration
BOT_TOKEN = "7672667666:AAGBkHf6VSFvfqLObKkavkZUxnDDe94Wgco"
SHEET_NAME = "Cab_Earnings"
CREDS_FILE = "cab-bot-credentials.json"
SHEET_KEY="1aJLyNDvRpbMW4DcvhWJk5-xNhRxK-Nq8RYPRbkOPB9o"

# Google Sheets setup
scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_KEY).sheet1

print(f"Authenticating as: {creds.service_account_email}")

# Conversation states
START_RIDE, END_RIDE, EARNINGS = range(3)
driver_data = {}

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚖 Cab Driver Bot 🚖\n\n"
        "/startride - Begin a new ride\n"
        "/endride - Finish current ride\n"
        "/help - Show instructions"
    )

async def start_ride(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    driver_data[user.id] = {
        'name': f"{user.first_name} {user.last_name or ''}",
        'start_time': datetime.now()
    }
    
    await update.message.reply_text(
        "✅ Ride started!\n"
        f"Start time: {driver_data[user.id]['start_time'].strftime('%H:%M:%S')}\n\n"
        "Use /endride when you complete the trip."
    )
    return START_RIDE

async def end_ride(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in driver_data:
        await update.message.reply_text("❌ No active ride! Use /startride first.")
        return ConversationHandler.END
    
    driver_data[user.id]['end_time'] = datetime.now()
    await update.message.reply_text(
        "💰 Please enter earnings for this ride (numbers only):"
    )
    return EARNINGS

async def record_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        earnings = float(update.message.text)
        if earnings <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Invalid amount! Please enter a positive number:")
        return EARNINGS

    # Calculate duration
    start = driver_data[user.id]['start_time']
    end = driver_data[user.id]['end_time']
    duration = round((end - start).total_seconds() / 60, 1)

    # Prepare data for sheet
    row = [
        user.id,
        driver_data[user.id]['name'],
        start.strftime("%Y-%m-%d %H:%M:%S"),
        end.strftime("%Y-%m-%d %H:%M:%S"),
        duration,
        earnings,
        start.strftime("%Y-%m-%d")
    ]

    # Save to Google Sheet
    sheet.append_row(row)
    
    await update.message.reply_text(
        f"📝 Ride recorded!\n"
        f"⏱ Duration: {duration} mins\n"
        f"💵 Earnings: ₹{earnings:.2f}\n\n"
        "Use /startride for next trip."
    )
    
    del driver_data[user.id]
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in driver_data:
        del driver_data[user.id]
    await update.message.reply_text("❌ Operation cancelled")
    return ConversationHandler.END

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('startride', start_ride)],
        states={
            START_RIDE: [
                CommandHandler('endride', end_ride)
            ],
            EARNINGS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, record_earnings)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(conv_handler)
    
    application.run_polling()

if __name__ == "__main__":
    main()