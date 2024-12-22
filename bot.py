import asyncio
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, 
                          filters, ContextTypes, CallbackQueryHandler)
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from bs4 import BeautifulSoup

# Конфигурация
TELEGRAM_BOT_TOKEN = "7842551713:AAEQheu5TOsj2rEvMywtZSFibGMsnImntO0"
GOOGLE_DRIVE_FOLDER_ID = "1dM1GwrkFlLRF_Pvs4f3Y_T0lMNZQaNW0"
CREDENTIALS_FILE = "/home/zaharevstaf/1.json"

# Глобальные переменные
chat_history = []
current_index = 0

# Подключение к Google Drive
def authenticate_google_drive():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=[
        "https://www.googleapis.com/auth/drive.readonly"
    ])
    return build("drive", "v3", credentials=creds)

def list_html_files(service):
    results = service.files().list(
        q=f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and mimeType='text/html'",
        fields="files(id, name)"
    ).execute()
    return results.get("files", [])

# Загрузка переписки с форматированием
def load_chat_history():
    global chat_history
    chat_history.clear()
    service = authenticate_google_drive()
    files = list_html_files(service)

    if not files:
        print("HTML-файлы не найдены в указанной папке Google Диска.")
        return

    files.sort(key=lambda x: x['name'])

    for file in files:
        try:
            request = service.files().get_media(fileId=file['id'])
            file_content = request.execute().decode("utf-8")

            soup = BeautifulSoup(file_content, "html.parser")
            messages = soup.find_all("div", class_="message")

            for msg in messages:
                sender = msg.find("div", class_="from_name")
                datetime = msg.find("div", class_="date")
                text = msg.find("div", class_="text")
                media = msg.find("a", class_="media_link")
                forwarded = msg.find("div", class_="forwarded")

                if datetime:
                    date, time = datetime.get("title", "").split(",")[0], datetime.get_text(strip=True)
                    timestamp = f"{date[:10]} {time[:5]}"

                if media:
                    media_type = "📷 Фото" if "photo" in media["class"] else \
                                 "🎥 Видео" if "video" in media["class"] else \
                                 "🎵 Голосовое сообщение"
                    chat_history.append({
                        "type": "media",
                        "content": media_type,
                        "url": media.get("href", "Файл не найден"),
                        "timestamp": timestamp
                    })

                if sender and datetime and text:
                    formatted_message = f"{sender.get_text(strip=True)} {timestamp}:\n{text.get_text(strip=True)}"
                    if forwarded:
                        formatted_message = f"🔁 Переслано от {forwarded.get_text(strip=True)}\n{formatted_message}"
                    chat_history.append({"type": "text", "content": formatted_message})
        except Exception as e:
            print(f"Ошибка при обработке файла {file['name']}: {e}")

# Отправка сообщений с задержкой
async def send_chat_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_index
    end_index = current_index + 100
    messages_to_send = chat_history[current_index:end_index]
    current_index = end_index

    for i, message in enumerate(messages_to_send):
        try:
            if message["type"] == "text":
                await update.effective_message.reply_text(message["content"])
            elif message["type"] == "media":
                await update.effective_message.reply_text(
                    f"{message['timestamp']} {message['content']} [Ссылка на файл]({message['url']})",
                    parse_mode="Markdown"
                )

            if (i + 1) % 2 == 0:  # Задержка каждые 2 сообщения
                await asyncio.sleep(0.5)
            if (i + 1) % 10 == 0:  # Задержка каждые 10 сообщений
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Ошибка при отправке сообщения: {e}")

    if current_index < len(chat_history):
        keyboard = [[InlineKeyboardButton("Далее", callback_data="next_batch")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.effective_message.reply_text("Нажмите 'Далее' для продолжения.", reply_markup=reply_markup)

# Основные команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("да", callback_data="option_yes"), InlineKeyboardButton("да, моя любовь!", callback_data="option_love")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Давайте я буду в Вас влюблена, а Вы в меня, и у нас будет лишь эпистолярный роман?", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "next_batch":
        await send_chat_history(update, context)
    elif query.data in ["option_yes", "option_love"]:
        await query.message.reply_text("Ты сделала меня счастливой! Теперь введи кодовую фразу для доступа к переписке.")

async def load_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_index
    user_input = update.message.text
    if user_input == "bolshe_ne_ydalyai_luchshe_stan'_moey_zhenoy":
        await update.message.reply_text("малышка, подожди, тырнэт грузит...")
        load_chat_history()
        current_index = 0
        await send_chat_history(update, context)
    else:
        await update.message.reply_text("Неверная кодовая фраза!")

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, load_chat))

    print("Бот запускается... Ожидание команд.")
    app.run_polling()
