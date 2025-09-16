import os
import logging
import sqlite3
from datetime import datetime, time
import pytz
from telegram import (
    Update,
    InputFile,
    InputMediaPhoto,
    InputMediaVideo,
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

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")   # теперь берём токен из переменной окружения
if not TOKEN:
    raise ValueError("❌ Не найден BOT_TOKEN в окружении. Задай его через fly secrets set BOT_TOKEN=...")

ADMIN_CHAT_ID = 1838738269
MAX_PHOTO_SIZE = 20 * 1024 * 1024  # 20MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


# URL вашего вебхука в Make (ЗАМЕНИТЕ НА СВОЙ!)
MAKE_WEBHOOK_URL = "https://hook.eu2.make.com/2rcn5ksonlssc9dbk5tnvrcm39kgq86m"

# Состояния диалога
(MAIN_MENU, GET_NAME, GET_PHONE, GET_TECH_TYPE, GET_PROBLEM, GET_MEDIA, CONFIRM) = range(7)

# Папки для хранения данных
MEDIA_DIR = "user_media"
os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs("media", exist_ok=True)

# Глобальные переменные
user_data = {}

# Тексты на разных языках
TEXTS = {
    'ru': {
        'welcome': "🔧 Добро пожаловать в сервисный центр!\nВыберите действие:",
        'select_language': "Выберите язык:",
        'enter_name': "Пожалуйста, введите ваше имя:",
        'enter_phone': "Пожалуйста, введите ваш номер телефона или нажмите кнопку ниже:",
        'select_tech': "Выберите тип техники:",
        'describe_problem': "Опишите проблему подробно:",
        'add_media': "📸 Пришлите фото/видео неисправности (макс. 10 файлов):\n• Фото до 20MB\n• Видео до 50MB",
        'confirm': "📋 Ваша заявка:\n\n👤 Имя: {name}\n📞 Телефон: {phone}\n🛠 Тип техники: {tech_type}\n❗ Проблема: {problem}\n\nВсё верно?",
        'confirm_buttons': ["✅ Да, всё верно", "❌ Нет, изменить данные"],
        'success': "✅ Заявка #{order_number} отправлена!\n\nМы получили вашу заявку и уже начали работу.\nМастер свяжется с вами в ближайшее время.",
        'error': "❌ Произошла ошибка при обработке вашей заявки. Пожалуйста, попробуйте позже.",
        'back': "↩️ Назад",
        'skip': "⏭ Пропустить",
        'cancel': "❌ Действие отменено. Чем ещё могу помочь?"
    },
    'uz': {
        'welcome': "🔧 Xizmat markaziga xush kelibsiz!\nHarakatni tanlang:",
        'select_language': "Tilni tanlang:",
        'enter_name': "Iltimos, ismingizni kiriting:",
        'enter_phone': "Iltimos, telefon raqamingizni kiriting yoki quyidagi tugmani bosing:",
        'select_tech': "Texnika turini tanlang:",
        'describe_problem': "Muammoni batafsil bayon qiling:",
        'add_media': "📸 Nosozlikning foto/video suratini yuboring (maks. 10 fayl):\n• Foto 20MB gacha\n• Video 50MB gacha",
        'confirm': "📋 Arizangiz:\n\n👤 Ism: {name}\n📞 Telefon: {phone}\n🛠 Texnika turi: {tech_type}\n❗ Muammo: {problem}\n\nHammasi to'g'rimi?",
        'confirm_buttons': ["✅ Ha, hammasi to'g'ri", "❌ Yo'q, o'zgartirmoqchiman"],
        'success': "✅ #{order_number} raqamli ariza jo'natildi!\n\nArizangiz qabul qilindi va ish boshlandi.\nTez orada usta siz bilan bog'lanadi.",
        'error': "❌ Arizangizni qayta ishlashda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.",
        'back': "↩️ Orqaga",
        'skip': "⏭ O'tkazish",
        'cancel': "❌ Harakat bekor qilindi. Yana qanday yordam bera olaman?"
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

# Flask app для UptimeRobot
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is alive and running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

def init_db():
    """Инициализация базы данных с проверкой существования столбцов"""
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()

    # Создаем таблицу orders, если не существует
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  order_number TEXT NOT NULL,
                  user_id INTEGER NOT NULL,
                  username TEXT,
                  name TEXT,
                  phone TEXT,
                  problem TEXT,
                  media_files TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Проверяем существование столбца tech_type
    c.execute("PRAGMA table_info(orders)")
    columns = [column[1] for column in c.fetchall()]
    if 'tech_type' not in columns:
        c.execute("ALTER TABLE orders ADD COLUMN tech_type TEXT")
    if 'language' not in columns:
        c.execute("ALTER TABLE orders ADD COLUMN language TEXT")

    # Создаем таблицу counters, если не существует
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
        # Правильный формат данных для Make
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

        # Убедимся, что все значения строковые
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
    text = TEXTS[language]['back']
    return ReplyKeyboardMarkup([
        [KeyboardButton("📱 " + ("Отправить мой номер" if language == 'ru' else "Mening raqamimni yuborish"), request_contact=True)],
        [KeyboardButton(text)]
    ], resize_keyboard=True)

async def cleanup_media(context: CallbackContext):
    """Очистка папки с медиа"""
    logger.info("Очистка папки user_media")
    for filename in os.listdir(MEDIA_DIR):
        file_path = os.path.join(MEDIA_DIR, filename)
        try:
            os.remove(file_path)
            logger.info(f"Удален файл: {filename}")
        except Exception as e:
            logger.error(f"Ошибка удаления файла {filename}: {e}")

async def start(update: Update, context: CallbackContext) -> int:
    """Начало диалога, выбор языка"""
    keyboard = [
        [InlineKeyboardButton("Русский", callback_data='lang_ru')],
        [InlineKeyboardButton("Oʻzbekcha", callback_data='lang_uz')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        with open("media/welcome.jpg.mp4", "rb") as photo:
            await update.message.reply_photo(
                photo=InputFile(photo),
                caption=TEXTS['ru']['select_language'],
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка загрузки welcome.jpg: {e}")
        await update.message.reply_text(
            TEXTS['ru']['select_language'],
            reply_markup=reply_markup
        )
    return MAIN_MENU

async def language_choice(update: Update, context: CallbackContext) -> int:
    """Обработка выбора языка"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    language = query.data.split('_')[1]
    user_data[user_id] = {'language': language, 'step': 'name'}

    try:
        await query.edit_message_text(
            text=TEXTS[language]['enter_name'],
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=TEXTS[language]['enter_name']
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
        reply_markup=contact_keyboard(language)
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
        reply_markup=reply_markup
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
        reply_markup=get_keyboard([TEXTS[language]['back']], language)
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
        reply_markup=get_keyboard([TEXTS[language]['skip'], TEXTS[language]['back']], language)
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

        file_size = os.path.getsize(file_path)
        if (ext == "jpg" and file_size > MAX_PHOTO_SIZE) or (ext == "mp4" and file_size > MAX_VIDEO_SIZE):
            os.remove(file_path)
            size_limit = "20MB" if ext == "jpg" else "50MB"
            await update.message.reply_text(
                f"⚠ Файл слишком большой. Максимальный размер: {size_limit}",
                reply_markup=get_keyboard([TEXTS[language]['skip'], TEXTS[language]['back']], language)
            )
            return GET_MEDIA

        user_data[user_id].setdefault('media', []).append(filename)
        logger.info(f"Сохранен файл: {filename} ({file_size/1024:.1f}KB)")

        remaining = 10 - len(user_data[user_id]['media'])
        if remaining > 0:
            await update.message.reply_text(
                f"📌 Файл сохранён. Можно отправить ещё {remaining} файлов или продолжить:",
                reply_markup=get_keyboard([TEXTS[language]['skip'], TEXTS[language]['back']], language)
            )
        else:
            await update.message.reply_text(
                "📌 Достигнут лимит вложений (10 файлов). Продолжаем:",
                reply_markup=get_keyboard([TEXTS[language]['skip']], language)
            )
    except Exception as e:
        logger.error(f"Ошибка сохранения файла {filename}: {e}")
        await update.message.reply_text(
            "❌ Не удалось сохранить файл. Попробуйте отправить другой файл:",
            reply_markup=get_keyboard([TEXTS[language]['skip']], language)
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
        reply_markup=get_keyboard(TEXTS[language]['confirm_buttons'], language)
    )
    return CONFIRM

async def send_to_admin(update: Update, context: CallbackContext) -> int:
    """Отправка заявки администратору"""
    user_id = update.effective_user.id
    if user_id not in user_data:
        language = 'ru'
        await update.message.reply_text(
            TEXTS[language]['error'],
            reply_markup=get_keyboard([TEXTS[language]['back']], language)
        )
        return MAIN_MENU

    try:
        language = user_data[user_id].get('language', 'ru')
        order_number = get_next_order_number()

        admin_text = (
            f"🚨 Новая заявка #{order_number}\n"
            f"👤 Имя: {user_data[user_id].get('name', 'Не указано')}\n"
            f"📞 Телефон: {user_data[user_id].get('phone', 'Не указано')}\n"
            f"🛠 Тип техники: {user_data[user_id].get('tech_type', 'Не указано')}\n"
            f"❗ Проблема: {user_data[user_id].get('problem', 'Не указано')}\n"
            f"🌐 Язык: {language}\n"
            f"📷 Медиафайлов: {len(user_data[user_id].get('media', []))} шт\n"
            f"🕒 Время: {datetime.now(MOSCOW_TZ).strftime('%H:%M %d.%m.%Y')}"
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

        # Подготавливаем данные для отправки в Make
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
            "source": "telegram_bot"
        }

        # Отправляем данные в Make
        import asyncio
        asyncio.create_task(send_to_make_webhook(make_data))

        # Отправка медиафайлов администратору
        media_files = user_data[user_id].get('media', [])

        # Кнопка для связи с пользователем
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📨 Написать пользователю",
                url=f"https://t.me/{update.effective_user.username}"
                if update.effective_user.username
                else f"tg://user?id={user_id}"
            )]
        ])

        if media_files:
            try:
                media_group = []
                for i, filename in enumerate(media_files[:10]):
                    file_path = os.path.join(MEDIA_DIR, filename)
                    if not os.path.exists(file_path):
                        continue
                    try:
                        with open(file_path, 'rb') as file:
                            if filename.endswith('.jpg'):
                                # Добавляем текст только к первому фото
                                caption = admin_text if i == 0 else ""
                                media_group.append(InputMediaPhoto(
                                    media=file,
                                    caption=caption
                                ))
                            elif filename.endswith('.mp4'):
                                # Добавляем текст только к первому видео
                                caption = admin_text if i == 0 else ""
                                media_group.append(InputMediaVideo(
                                    media=file,
                                    caption=caption
                                ))
                    except Exception as e:
                        logger.error(f"Ошибка обработки {filename}: {e}")

                if media_group:
                    await context.bot.send_media_group(
                        chat_id=ADMIN_CHAT_ID,
                        media=media_group,
                        disable_notification=True
                    )
                    # Отправляем кнопку отдельным сообщением
                    await context.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text="📨 Связь с пользователем:",
                        reply_markup=keyboard
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки медиагруппы: {e}")
                # Если не удалось отправить медиа, отправляем текстовое сообщение с кнопкой
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_text + "\n\n⚠ Не удалось отправить вложения",
                    reply_markup=keyboard
                )
        else:
            # Если нет медиафайлов, отправляем одно текстовое сообщение с кнопкой
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_text,
                reply_markup=keyboard
            )

        # Подтверждение пользователю
        try:
            with open("media/goodbye.jpg", 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=TEXTS[language]['success'].format(order_number=order_number),
                    reply_markup=get_keyboard([TEXTS[language]['back']], language)
                )
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            await update.message.reply_text(
                TEXTS[language]['success'].format(order_number=order_number),
                reply_markup=get_keyboard([TEXTS[language]['back']], language)
            )

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        await update.message.reply_text(
            TEXTS[language]['error'],
            reply_markup=get_keyboard([TEXTS[language]['back']], language)
        )
    finally:
        # Очистка данных
        if user_id in user_data:
            for filename in user_data[user_id].get('media', []):
                try:
                    os.remove(os.path.join(MEDIA_DIR, filename))
                except Exception as e:
                    logger.error(f"Ошибка удаления файла {filename}: {e}")
            del user_data[user_id]

    return MAIN_MENU

async def cancel(update: Update, context: CallbackContext) -> int:
    """Отмена текущего действия"""
    user_id = update.effective_user.id
    language = user_data.get(user_id, {}).get('language', 'ru')

    if user_id in user_data:
        for filename in user_data[user_id].get('media', []):
            try:
                os.remove(os.path.join(MEDIA_DIR, filename))
            except Exception as e:
                logger.error(f"Ошибка удаления файла {filename}: {e}")
        del user_data[user_id]

    await update.message.reply_text(
        TEXTS[language]['cancel'],
        reply_markup=get_keyboard([TEXTS[language]['back']], language)
    )
    return MAIN_MENU

async def about(update: Update, context: CallbackContext) -> None:
    """Информация о сервисе"""
    user_id = update.effective_user.id
    language = user_data.get(user_id, {}).get('language', 'ru')

    text = {
        'ru': "🔧 О нашем сервисе:\n\n• Профессиональный ремонт бытовой техники\n• Официальная гарантия до 2 лет\n• Выезд мастера в день обращения\n• Оригинальные запчасти\n\n⏰ Часы работы: Пн-Пт 9:00-18:00",
        'uz': "🔧 Bizning xizmatimiz haqida:\n\n• Maishiy texnikani professional ta'mirlash\n• 2 yilgacha rasmiy kafolat\n• Masterning xizmat kuni ichida kelishi\n• Original ehtiyot qismlar\n\n⏰ Ish vaqti: Dush-Jum 9:00-18:00"
    }

    await update.message.reply_text(
        text[language],
        reply_markup=get_keyboard([TEXTS[language]['back']], language)
    )

async def contacts(update: Update, context: CallbackContext) -> None:
    """Контактная информация"""
    user_id = update.effective_user.id
    language = user_data.get(user_id, {}).get('language', 'ru')

    text = {
        'ru': "📞 Наши контакты:\n\n📍 Адрес: г. Ташкент, ул. Олтин тепа 233\n☎ Телефон: +998884792901\n📧 Email: fixservise@sbk.ru\n🌐 Сайт: zorservice.uz\n\n🚗 Бесплатная парковка для клиентов",
        'uz': "📞 Bizning kontaktlarimiz:\n\n📍 Manzil: Toshkent sh., Oltin tepa ko'chasi 233\n☎ Telefon: +998884792901\n📧 Email: fixservise@sbk.ru\n🌐 Vebsayt: zorservice.uz\n\n🚗 Mijozlar uchun bepul avtoturargoh"
    }

    await update.message.reply_text(
        text[language],
        reply_markup=get_keyboard([TEXTS[language]['back']], language)
    )

def main():
    """Запуск бота"""
    keep_alive()  # Запускаем Flask-сервер для UptimeRobot
    init_db()

    application = Application.builder().token(TOKEN).build()

    # Очистка медиафайлов каждый день в 23:00
    cleanup_time = time(23, 0, tzinfo=MOSCOW_TZ)
    application.job_queue.run_daily(
        cleanup_media,
        time=cleanup_time,
        days=(0, 1, 2, 3, 4, 5, 6),
        name="daily_media_cleanup"
    )

    # Обработчики команд
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(language_choice, pattern='^lang_'),
                MessageHandler(filters.Regex('^ℹ️ О сервисе$') | filters.Regex('^📞 Контакты$'), about),
            ],
            GET_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name),
            ],
            GET_PHONE: [
                MessageHandler(filters.TEXT | filters.CONTACT, get_phone),
            ],
            GET_TECH_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_tech_type),
            ],
            GET_PROBLEM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_problem),
            ],
            GET_MEDIA: [
                MessageHandler(filters.PHOTO | filters.VIDEO, handle_media),
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_data),
            ],
            CONFIRM: [
                MessageHandler(filters.Regex('^(✅ Да, всё верно|✅ Ha, hammasi to\'g\'ri)$'), send_to_admin),
                MessageHandler(filters.Regex('^(❌ Нет, изменить данные|❌ Yo\'q, o\'zgartirmoqchiman)$'), start),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Regex('^↩️ Назад$') | filters.Regex('^↩️ Orqaga$'), cancel))
    application.add_handler(MessageHandler(filters.Regex('^ℹ️ О сервисе$') | filters.Regex('^📞 Контакты$'), about))

    application.run_polling()

if __name__ == '__main__':
    main()
# trigger deploy
