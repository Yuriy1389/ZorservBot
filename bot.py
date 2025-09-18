import os 
import logging
import sqlite3
import asyncio
import requests
from datetime import datetime
import pytz
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    ConversationHandler,
    filters,
    CallbackQueryHandler
)
from flask import Flask, request

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ Не найден BOT_TOKEN в окружении")

PORT = int(os.environ.get('PORT', 8080))
ADMIN_CHAT_ID = 1838738269
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
MAKE_WEBHOOK_URL = "https://hook.eu2.make.com/2rcn5ksonlssc9dbk5tnvrcm39kgq86m"

# Состояния диалога
(MAIN_MENU, GET_NAME, GET_PHONE, GET_TECH_TYPE, GET_PROBLEM, GET_MEDIA, CONFIRM) = range(7)

# Папки для хранения данных
MEDIA_DIR = "user_media"
os.makedirs(MEDIA_DIR, exist_ok=True)

# Глобальные переменные
user_data = {}
application = None

# Тексты на разных языках
TEXTS = {
    'ru': {
        'welcome': "👋 <b>Здравствуйте, меня зовут Zorservbot!</b>\nЯ помогу оформить Вам заказ!\n\n<b>Salom, mening ismim Zorservbot!</b>\nMen sizga buyurtma berishga yordam beraman!\n\n🌐 <b>Выберите язык / Tilni tanlang</b>",
        'enter_name': "👤 <b>Введите ваше имя / Ismingizni kiriting:</b>",
        'enter_phone': "📞 <b>Введите ваш номер телефона / Telefon raqamingizni kiriting:</b>\n\nИли нажмите кнопку ниже / Yoki quyidagi tugmani bosing:",
        'select_tech': "🛠 <b>Выберите тип техники / Texnika turini tanlang:</b>",
        'describe_problem': "❗ <b>Опишите проблему подробно / Muammoni batafsil bayon qiling:</b>",
        'add_media': "📸 <b>Пришлите фото/видео неисправности / Nosozlikning foto/video suratini yuboring</b>\n\n• Фото до 20MB / Foto 20MB gacha\n• Видео до 50MB / Video 50MB gacha\n• Макс. 10 файлов / Maks. 10 fayl",
        'confirm': "📋 <b>Ваша заявка / Arizangiz:</b>\n\n"
                  "👤 <b>Имя / Ism:</b> {name}\n"
                  "📞 <b>Телефон / Telefon:</b> {phone}\n"
                  "🛠 <b>Тип техники / Texnika turi:</b> {tech_type}\n"
                  "❗ <b>Проблема / Muammo:</b> {problem}\n\n"
                  "<b>Всё верно? / Hammasi to'g'rimi?</b>",
        'confirm_buttons': ["✅ Да, всё верно", "❌ Нет, изменить данные"],
        'success': "✅ <b>Заявка #{order_number} отправлена! / #{order_number} raqamli ariza jo'natildi!</b>\n\nМы получили вашу заявку и уже начали работу. / Arizangiz qabul qilindi va ish boshlandi.\nМастер свяжется с вами в ближайшее время. / Tez orada usta siz bilan bog'lanadi.",
        'error': "❌ Произошла ошибка при обработке вашей заявки. Пожалуйста, попробуйте позже. / Arizangizni qayta ishlashda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.",
        'back': "↩️ Назад / Orqaga",
        'skip': "⏭ Пропустить / O'tkazish",
        'cancel': "❌ Действие отменено. Чем ещё могу помочь? / Harakat bekor qilindi. Yana qanday yordam bera olaman?",
        'start_again': "🔄 Начать заново / Qayta boshlash"
    },
    'uz': {
        'welcome': "👋 <b>Здравствуйте, меня зовут Zorservbot!</b>\nЯ помогу оформить Вам заказ!\n\n<b>Salom, mening ismim Zorservbot!</b>\nMen sizga buyurtma berishga yordam beraman!\n\n🌐 <b>Выберите язык / Tilni tanlang</b>",
        'enter_name': "👤 <b>Введите ваше имя / Ismingizni kiriting:</b>",
        'enter_phone': "📞 <b>Введите ваш номер телефона / Telefon raqamingizni kiriting:</b>\n\nИли нажмите кнопку ниже / Yoki quyidagi tugmani bosing:",
        'select_tech': "🛠 <b>Выберите тип техники / Texnika turini tanlang:</b>",
        'describe_problem': "❗ <b>Опишите проблему подробно / Muammoni batafsil bayon qiling:</b>",
        'add_media': "📸 <b>Пришлите фото/видео неисправности / Nosozlikning foto/video suratini yuboring</b>\n\n• Фото до 20MB / Foto 20MB gacha\n• Видео до 50MB / Video 50MB gacha\n• Макс. 10 файлов / Maks. 10 fayl",
        'confirm': "📋 <b>Ваша заявка / Arizangiz:</b>\n\n"
                  "👤 <b>Имя / Ism:</b> {name}\n"
                  "📞 <b>Телефон / Telefon:</b> {phone}\n"
                  "🛠 <b>Тип техники / Texnika turi:</b> {tech_type}\n"
                  "❗ <b>Проблема / Muammo:</b> {problem}\n\n"
                  "<b>Всё верно? / Hammasi to'g'rimi?</b>",
        'confirm_buttons': ["✅ Ha, hammasi to'g'ri", "❌ Yo'q, o'zgartirmoqchiman"],
        'success': "✅ <b>Заявка #{order_number} отправлена! / #{order_number} raqamli ariza jo'natildi!</b>\n\nМы получили вашу заявку и уже начали работу. / Arizangiz qabul qilindi va ish boshlandi.\nМастер свяжется с вами в ближайшее время. / Tez orada usta siz bilan bog'lanadi.",
        'error': "❌ Произошла ошибка при обработке вашей заявки. Пожалуйста, попробуйте позже. / Arizangizni qayta ishlashda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.",
        'back': "↩️ Назад / Orqaga",
        'skip': "⏭ Пропустить / O'tkazish",
        'cancel': "❌ Действие отменено. Чем ещё могу помочь? / Harakat bekor qilindi. Yana qanday yordam bera olaman?",
        'start_again': "🔄 Начать заново / Qayta boshlash"
    }
}

TECH_TYPES = {
    'ru': [
        "Стиральная машина",
        "Духовка",
        "Электроплита",
        "Холодильник",
        "Посудомойка",
        "Кофемашина",
        "Робот-пылесос"
    ],
    'uz': [
        "Kir yuvish mashinasi",
        "Pech",
        "Elektroplita",
        "Muzlatgich",
        "Idish yuvish mashinasi",
        "Kofe mashinasi",
        "Changyutgich robot"
    ]
}

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  order_number TEXT NOT NULL,
                  user_id INTEGER NOT NULL,
                  username TEXT,
                  name TEXT,
                  phone TEXT,
                  tech_type TEXT,
                  problem TEXT,
                  media_files TEXT,
                  language TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS counters
                 (id INTEGER PRIMARY KEY,
                  last_order_number INTEGER,
                  last_reset_date TEXT)''')

    c.execute("SELECT COUNT(*) FROM counters WHERE id = 1")
    if c.fetchone()[0] == 0:
        current_date = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d')
        c.execute("INSERT INTO counters (id, last_order_number, last_reset_date) VALUES (1, 0, ?)", (current_date,))

    conn.commit()
    conn.close()

def get_next_order_number():
    """Генерация номера заявки"""
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()

    try:
        current_date = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d')
        c.execute("SELECT last_reset_date, last_order_number FROM counters WHERE id = 1")
        result = c.fetchone()

        if not result:
            last_order_number = 0
            c.execute("INSERT INTO counters (id, last_order_number, last_reset_date) VALUES (1, 0, ?)", (current_date,))
        else:
            last_reset_date, last_order_number = result
            if last_reset_date != current_date:
                last_order_number = 0
                c.execute("UPDATE counters SET last_order_number = 0, last_reset_date = ? WHERE id = 1", (current_date,))

        new_number = last_order_number + 1
        c.execute("UPDATE counters SET last_order_number = ? WHERE id = 1", (new_number,))
        conn.commit()

        return f"{datetime.now(MOSCOW_TZ).strftime('%d%m%Y')}-{new_number:04d}"

    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных: {e}")
        return f"EMG-{datetime.now(MOSCOW_TZ).strftime('%d%m%Y%H%M%S')}"
    finally:
        conn.close()

async def send_to_make_webhook(order_data):
    """Отправка данных заявки в Make"""
    try:
        make_payload = {
            "chat_id": order_data.get("user_id", 0),
            "username": order_data.get("username", "Не указано"),
            "name": order_data.get("name", "Не указано"),
            "phone": order_data.get("phone", "Не указано"),
            "tech_type": order_data.get("tech_type", "Не указано"),
            "problem": order_data.get("problem", "Не указано"),
            "language": order_data.get("language", "ru"),
            "order_number": order_data.get("order_number", "Без номера"),
            "media_count": order_data.get("media_count", 0),
            "source": "telegram_bot"
        }

        for key, value in make_payload.items():
            if value is None:
                make_payload[key] = ""
            elif not isinstance(value, (str, int, float)):
                make_payload[key] = str(value)

        logger.info(f"Отправка данных в Make: {make_payload}")

        response = requests.post(
            MAKE_WEBHOOK_URL,
            json=make_payload,
            timeout=10
        )

        if response.status_code == 200:
            logger.info(f"✅ Данные успешно отправлены в Make для заявки {order_data['order_number']}")
            return True
        else:
            logger.error(f"❌ Ошибка отправки в Make: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке в Make: {e}")
        return False

def get_keyboard(buttons, language='ru'):
    """Создает клавиатуру из списка кнопок"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(button)] for button in buttons],
        resize_keyboard=True
    )

def contact_keyboard(language='ru'):
    """Клавиатура для отправки контакта"""
    if language == 'ru':
        text = "↩️ Назад / Orqaga"
        button_text = "📱 Отправить мой номер / Mening raqamimni yuborish"
    else:
        text = "↩️ Orqaga / Назад"
        button_text = "📱 Mening raqamimni yuborish / Отправить мой номер"
    
    return ReplyKeyboardMarkup([
        [KeyboardButton(button_text, request_contact=True)],
        [KeyboardButton(text)]
    ], resize_keyboard=True)

def start_keyboard(language='ru'):
    """Клавиатура для кнопки Старт"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("/start")]
    ], resize_keyboard=True)

async def start(update: Update, context: CallbackContext) -> int:
    """Начало диалога, выбор языка"""
    keyboard = [
        [InlineKeyboardButton("Русский язык", callback_data='lang_ru')],
        [InlineKeyboardButton("Узбекский язык", callback_data='lang_uz')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        TEXTS['ru']['welcome'],
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return MAIN_MENU

async def language_choice(update: Update, context: CallbackContext) -> int:
    """Обработка выбора языка"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    language = query.data.split('_')[1]
    user_data[user_id] = {'language': language, 'step': 'name'}

    # Обновляем сообщение с убранными кнопками
    welcome_text = TEXTS[language]['welcome'].split('🌐')[0]
    await query.edit_message_text(
        text=welcome_text,
        parse_mode='HTML'
    )
    
    # Отправляем запрос имени
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=TEXTS[language]['enter_name'],
        parse_mode='HTML'
    )
    
    return GET_NAME

async def get_name(update: Update, context: CallbackContext) -> int:
    """Получение имени пользователя"""
    user_id = update.effective_user.id
    language = user_data[user_id].get('language', 'ru')
    user_data[user_id]['name'] = update.message.text
    user_data[user_id]['step'] = 'phone'

    await update.message.reply_text(
        TEXTS[language]['enter_phone'],
        reply_markup=contact_keyboard(language),
        parse_mode='HTML'
    )
    return GET_PHONE

async def get_phone(update: Update, context: CallbackContext) -> int:
    """Получение номера телефона"""
    user_id = update.effective_user.id
    language = user_data[user_id].get('language', 'ru')

    if update.message.contact:
        user_data[user_id]['phone'] = update.message.contact.phone_number
    else:
        user_data[user_id]['phone'] = update.message.text

    user_data[user_id]['step'] = 'tech_type'

    buttons = TECH_TYPES[language]
    reply_markup = ReplyKeyboardMarkup(
        [buttons[i:i+2] for i in range(0, len(buttons), 2)],
        resize_keyboard=True
    )

    await update.message.reply_text(
        TEXTS[language]['select_tech'],
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return GET_TECH_TYPE

async def get_tech_type(update: Update, context: CallbackContext) -> int:
    """Получение типа техники"""
    user_id = update.effective_user.id
    language = user_data[user_id].get('language', 'ru')
    user_data[user_id]['tech_type'] = update.message.text
    user_data[user_id]['step'] = 'problem'

    await update.message.reply_text(
        TEXTS[language]['describe_problem'],
        reply_markup=get_keyboard([TEXTS[language]['back']], language),
        parse_mode='HTML'
    )
    return GET_PROBLEM

async def get_problem(update: Update, context: CallbackContext) -> int:
    """Получение описания проблемы"""
    user_id = update.effective_user.id
    language = user_data[user_id].get('language', 'ru')
    user_data[user_id]['problem'] = update.message.text
    user_data[user_id]['step'] = 'media'

    await update.message.reply_text(
        TEXTS[language]['add_media'],
        reply_markup=get_keyboard([TEXTS[language]['skip'], TEXTS[language]['back']], language),
        parse_mode='HTML'
    )
    return GET_MEDIA

async def handle_media(update: Update, context: CallbackContext) -> int:
    """Обработка медиафайлов"""
    user_id = update.effective_user.id
    language = user_data[user_id].get('language', 'ru')

    if update.message.text == TEXTS[language]['skip']:
        return await confirm_data(update, context)

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file = await context.bot.get_file(file_id)
        ext = "jpg"
    elif update.message.video:
        file_id = update.message.video.file_id
        file = await context.bot.get_file(file_id)
        ext = "mp4"
    else:
        return await confirm_data(update, context)

    filename = f"{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
    file_path = os.path.join(MEDIA_DIR, filename)

    try:
        await file.download_to_drive(file_path)
        user_data[user_id].setdefault('media', []).append(filename)
        
        remaining = 10 - len(user_data[user_id]['media'])
        if remaining > 0:
            await update.message.reply_text(
                f"📌 Файл сохранён. Можно отправить ещё {remaining} файлов или продолжить:",
                reply_markup=get_keyboard([TEXTS[language]['skip'], TEXTS[language]['back']], language),
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "📌 Достигнут лимит вложений (10 файлов). Продолжаем:",
                reply_markup=get_keyboard([TEXTS[language]['skip']], language),
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Ошибка сохранения файла {filename}: {e}")
        await update.message.reply_text(
            "❌ Не удалось сохранить файл. Попробуйте отправить другой файл:",
            reply_markup=get_keyboard([TEXTS[language]['skip']], language),
            parse_mode='HTML'
        )

    return GET_MEDIA

async def confirm_data(update: Update, context: CallbackContext) -> int:
    """Подтверждение данных перед отправкой"""
    user_id = update.effective_user.id
    language = user_data[user_id].get('language', 'ru')

    confirm_text = TEXTS[language]['confirm'].format(
        name=user_data[user_id].get('name', '-'),
        phone=user_data[user_id].get('phone', '-'),
        tech_type=user_data[user_id].get('tech_type', '-'),
        problem=user_data[user_id].get('problem', '-')
    )

    await update.message.reply_text(
        confirm_text,
        reply_markup=get_keyboard(TEXTS[language]['confirm_buttons'], language),
        parse_mode='HTML'
    )
    return CONFIRM

async def send_to_admin(update: Update, context: CallbackContext) -> int:
    """Отправка заявки администратору"""
    user_id = update.effective_user.id
    if user_id not in user_data:
        language = 'ru'
        await update.message.reply_text(
            TEXTS[language]['error'],
            reply_markup=get_keyboard([TEXTS[language]['back']], language),
            parse_mode='HTML'
        )
        return MAIN_MENU

    try:
        language = user_data[user_id].get('language', 'ru')
        order_number = get_next_order_number()

        admin_text = (
            f"🚨 <b>Новая заявка #{order_number}</b>\n\n"
            f"👤 <b>Имя:</b> {user_data[user_id].get('name', 'Не указано')}\n"
            f"📞 <b>Телефон:</b> {user_data[user_id].get('phone', 'Не указано')}\n"
            f"🛠 <b>Тип техники:</b> {user_data[user_id].get('tech_type', 'Не указано')}\n"
            f"❗ <b>Проблема:</b> {user_data[user_id].get('problem', 'Не указано')}\n"
            f"🌐 <b>Язык:</b> {language}\n"
            f"📷 <b>Медиафайлов:</b> {len(user_data[user_id].get('media', []))} шт\n"
            f"🕒 <b>Время:</b> {datetime.now(MOSCOW_TZ).strftime('%H:%M %d.%m.%Y')}"
        )

        # Сохраняем в базу данных
        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        c.execute('''INSERT INTO orders
                    (order_number, user_id, username, name, phone, tech_type, problem, media_files, language)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (order_number,
                user_id,
                update.effective_user.username,
                user_data[user_id].get('name'),
                user_data[user_id].get('phone'),
                user_data[user_id].get('tech_type'),
                user_data[user_id].get('problem'),
                ",".join(user_data[user_id].get('media', [])),
                language))
        conn.commit()
        conn.close()

        # Отправляем данные в Make
        make_data = {
            "order_number": order_number,
            "user_id": user_id,
            "username": update.effective_user.username or "Не указано",
            "name": user_data[user_id].get('name', 'Не указано'),
            "phone": user_data[user_id].get('phone', 'Не указано'),
            "tech_type": user_data[user_id].get('tech_type', 'Не указано'),
            "problem": user_data[user_id].get('problem', 'Не указано'),
            "language": language,
            "media_count": len(user_data[user_id].get('media', [])),
            "source": "telegram"
        }

        # Отправляем данные в Make
        await send_to_make_webhook(make_data)

        # Отправляем уведомление администратору
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_text,
            parse_mode='HTML'
        )

        # Отправляем подтверждение пользователю
        success_text = TEXTS[language]['success'].format(order_number=order_number)
        await update.message.reply_text(
            success_text,
            reply_markup=start_keyboard(language),
            parse_mode='HTML'
        )

        # Очищаем данные пользователя
        if user_id in user_data:
            del user_data[user_id]

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при отправке заявки: {e}")
        language = user_data.get(user_id, {}).get('language', 'ru')
        await update.message.reply_text(
            TEXTS[language]['error'],
            reply_markup=get_keyboard([TEXTS[language]['back']], language),
            parse_mode='HTML'
        )
        return MAIN_MENU

async def cancel(update: Update, context: CallbackContext) -> int:
    """Отмена диалога"""
    user_id = update.effective_user.id
    language = user_data.get(user_id, {}).get('language', 'ru')
    
    if user_id in user_data:
        del user_data[user_id]
    
    await update.message.reply_text(
        TEXTS[language]['cancel'],
        reply_markup=start_keyboard(language),
        parse_mode='HTML'
    )
    return ConversationHandler.END

async def error_handler(update: Update, context: CallbackContext) -> None:
    """Обработка ошибок"""
    logger.error(f"Ошибка при обработке обновления: {context.error}")

# Создаем Flask приложение
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running and ready to receive webhooks!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик webhook от Telegram"""
    if application is None:
        return "Application not initialized", 500
        
    try:
        # Получаем обновление от Telegram
        update_data = request.get_json()
        update = Update.de_json(update_data, application.bot)
        
        # Обрабатываем обновление асинхронно
        asyncio.run(application.process_update(update))
        
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        return "Error", 500

async def main() -> None:
    """Основная функция запуска бота"""
    global application
    
    # Инициализация базы данных
    init_db()
    
    # Создание приложения
    application = Application.builder().token(TOKEN).build()

    # Настройка ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(language_choice, pattern='^lang_')],
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)
            ],
            GET_TECH_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tech_type)],
            GET_PROBLEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_problem)],
            GET_MEDIA: [
                MessageHandler(filters.PHOTO | filters.VIDEO, handle_media),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media)
            ],
            CONFIRM: [
                MessageHandler(filters.Regex('^(✅ Да, всё верно|✅ Ha, hammasi to\'g\'ri)$'), send_to_admin),
                MessageHandler(filters.Regex('^(❌ Нет, изменить данные|❌ Yo\'q, o\'zgartirmoqchiman)$'), start)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False,
        allow_reentry=True
    )

    # Добавление обработчиков
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    # Устанавливаем webhook
    webhook_url = "https://zorservbot.fly.dev/webhook"
    logger.info(f"Устанавливаем webhook: {webhook_url}")
    
    try:
        # Очищаем предыдущий webhook и устанавливаем новый
        await application.bot.delete_webhook()
        await asyncio.sleep(1)
        await application.bot.set_webhook(webhook_url)
        logger.info("Webhook успешно установлен!")
        return True
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}")
        return False

def run_bot():
    """Запуск бота"""
    global application
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        webhook_success = loop.run_until_complete(main())

        if webhook_success:
            logger.info("Запускаем Flask сервер для webhook")
            from waitress import serve
            serve(app, host="0.0.0.0", port=PORT)
        else:
            logger.error("Не удалось установить webhook, запускаем polling")
            # ⚠️ run_polling больше не coroutine
            application.run_polling()
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        try:
            application.run_polling()
        except:
            logger.critical("Бот не может быть запущен")
