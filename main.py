import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InputFile

bot = Bot(token="", parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

ADMINS = []  # ID администраторов


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS welcome_message (
            id INTEGER PRIMARY KEY,
            message_text TEXT,
            photo_path TEXT
        )
    ''')
    cursor.execute('''
    CREATE
    TABLE
    IF
    NOT
    EXISTS
    channels(
        id
    INTEGER
    PRIMARY
    KEY
    AUTOINCREMENT,
    channel_name
    TEXT,
    channel_url
    TEXT
    )
    ''')

    # Добавляем стандартное приветственное сообщение, если его нет
    cursor.execute('SELECT * FROM welcome_message')
    if not cursor.fetchone():
        cursor.execute('INSERT INTO welcome_message (id, message_text, photo_path) VALUES (1, "<b>.</b>", NULL)')

    conn.commit()
    conn.close()

init_db()

# States для FSM
class Form(StatesGroup):
    waiting_for_welcome_message = State()
    waiting_for_welcome_photo = State()
    waiting_for_channel_name = State()
    waiting_for_channel_url = State()

def insert_user(telegram_id):
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?;', (telegram_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute('INSERT INTO USERS(telegram_id, balance) VALUES (?, 0);', (telegram_id,))
        conn.commit()
    conn.close()

def get_welcome_message():
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()
    cursor.execute('SELECT message_text, photo_path FROM welcome_message WHERE id = 1')
    message = cursor.fetchone()
    conn.close()
    return message

def update_welcome_message(new_text, photo_path=None):
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()
    if photo_path:
        cursor.execute('UPDATE welcome_message SET message_text = ?, photo_path = ? WHERE id = 1', (new_text, photo_path))
    else:
        cursor.execute('UPDATE welcome_message SET message_text = ? WHERE id = 1', (new_text,))
    conn.commit()
    conn.close()

def get_channels():
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM channels')
    channels = cursor.fetchall()
    conn.close()
    return channels

def add_channel(name, url):
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO channels (channel_name, channel_url) VALUES (?, ?)', (name, url))
    conn.commit()
    conn.close()

def delete_channel(channel_id):
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM channels WHERE id = ?', (channel_id,))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE date(registration_date) = date("now")')
    new_today = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE date(registration_date) >= date("now", "-7 days")')
    new_week = cursor.fetchone()[0]

    conn.close()

    return {
        'total_users': total_users,
        'new_today': new_today,
        'new_week': new_week
    }


async def send_welcome_message(user_id):
    welcome_data = get_welcome_message()
    welcome_text = welcome_data[0]
    photo_path = welcome_data[1]
    channels = get_channels()

    kb = types.InlineKeyboardMarkup()

    # Группируем каналы по 2 и создаем ряды кнопок
    for i in range(0, len(channels), 2):
        row_channels = channels[i:i + 2]
        row_buttons = [
            types.InlineKeyboardButton(text='Подписаться', url=channel[2])
            for channel in row_channels
        ]
        kb.row(*row_buttons)

    if photo_path:
        try:
            photo = InputFile(photo_path)
            await bot.send_photo(chat_id=user_id, photo=photo, caption=welcome_text, reply_markup=kb)
        except Exception as e:
            print(f"Ошибка при отправке фото: {e}")
            await bot.send_message(chat_id=user_id, text=welcome_text, reply_markup=kb)
    else:
        await bot.send_message(chat_id=user_id, text=welcome_text, reply_markup=kb)


@dp.message_handler(commands='start')
async def start_msg(message: types.Message):
    insert_user(message.from_user.id)
    await send_welcome_message(message.from_user.id)

@dp.chat_join_request_handler()
async def start1(update: types.ChatJoinRequest):
    insert_user(update.from_user.id)
    await send_welcome_message(update.from_user.id)

# Админ панель
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMINS:
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('📊 Статистика')
    btn2 = types.KeyboardButton('✏️ Изменить приветствие')
    btn3 = types.KeyboardButton('🖼️ Изменить фото приветствия')
    btn4 = types.KeyboardButton('➕ Добавить канал')
    btn5 = types.KeyboardButton('➖ Удалить канал')
    btn6 = types.KeyboardButton('📋 Просмотреть каналы')
    btn7 = types.KeyboardButton('📢 Рассылка')
    kb.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)

    await message.answer('👨‍💻 Админ-панель:', reply_markup=kb)

@dp.message_handler(lambda message: message.text == '📊 Статистика' and message.from_user.id in ADMINS)
async def show_stats(message: types.Message):
    stats = get_stats()

    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"🆕 Новых за сегодня: <b>{stats['new_today']}</b>\n"
        f"📅 Новых за неделю: <b>{stats['new_week']}</b>"
    )

    await message.answer(text)

@dp.message_handler(lambda message: message.text == '✏️ Изменить приветствие' and message.from_user.id in ADMINS)
async def change_welcome(message: types.Message):
    welcome_data = get_welcome_message()
    await message.answer(f'📝 Текущее приветственное сообщение:\n{welcome_data[0]}\n\nОтправьте новое приветственное сообщение:')
    await Form.waiting_for_welcome_message.set()

@dp.message_handler(state=Form.waiting_for_welcome_message)
async def process_welcome_message(message: types.Message, state: FSMContext):
    update_welcome_message(message.text)
    await state.finish()
    await message.answer('✅ Приветственное сообщение обновлено!')

@dp.message_handler(lambda message: message.text == '🖼️ Изменить фото приветствия' and message.from_user.id in ADMINS)
async def change_welcome_photo(message: types.Message):
    await message.answer('📸 Отправьте новое фото для приветственного сообщения (или "удалить" чтобы удалить текущее фото):')
    await Form.waiting_for_welcome_photo.set()

@dp.message_handler(content_types=['photo'], state=Form.waiting_for_welcome_photo)
async def process_welcome_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path

    # Сохраняем фото
    photo_path = f"welcome_photo_{message.from_user.id}.jpg"
    await bot.download_file(file_path, photo_path)

    # Обновляем в базе данных
    welcome_data = get_welcome_message()
    update_welcome_message(welcome_data[0], photo_path)

    await state.finish()
    await message.answer('✅ Фото приветственного сообщения обновлено!')

@dp.message_handler(lambda message: message.text.lower() == 'удалить', state=Form.waiting_for_welcome_photo)
async def remove_welcome_photo(message: types.Message, state: FSMContext):
    welcome_data = get_welcome_message()
    update_welcome_message(welcome_data[0], None)

    await state.finish()
    await message.answer('✅ Фото приветственного сообщения удалено!')

@dp.message_handler(lambda message: message.text == '➕ Добавить канал' and message.from_user.id in ADMINS)
async def add_channel_start(message: types.Message):
    await message.answer('Введите название канала:')
    await Form.waiting_for_channel_name.set()

@dp.message_handler(state=Form.waiting_for_channel_name)
async def process_channel_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['channel_name'] = message.text

    await message.answer('Теперь введите ссылку на канал:')
    await Form.waiting_for_channel_url.set()

@dp.message_handler(state=Form.waiting_for_channel_url)
async def process_channel_url(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        channel_name = data['channel_name']
        channel_url = message.text

    add_channel(channel_name, channel_url)
    await state.finish()
    await message.answer(f'✅ Канал "{channel_name}" добавлен!')

@dp.message_handler(lambda message: message.text == '➖ Удалить канал' and message.from_user.id in ADMINS)
async def delete_channel_start(message: types.Message):
    channels = get_channels()
    if not channels:
        await message.answer('❌ Нет каналов для удаления.')
        return

    kb = types.InlineKeyboardMarkup()
    for channel in channels:
        kb.add(types.InlineKeyboardButton(
            text=f'{channel[1]}',
            callback_data=f'delete_{channel[0]}'
        ))

    await message.answer('Выберите канал для удаления:', reply_markup=kb)

@dp.callback_query_handler(lambda query: query.data.startswith('delete_') and query.from_user.id in ADMINS)
async def process_delete_channel(query: types.CallbackQuery):
    channel_id = int(query.data.split('_')[1])
    delete_channel(channel_id)
    await query.message.answer('✅ Канал удален!')
    await query.answer()

@dp.message_handler(lambda message: message.text == '📋 Просмотреть каналы' and message.from_user.id in ADMINS)
async def view_channels(message: types.Message):
    channels = get_channels()
    if not channels:
        await message.answer('❌ Нет добавленных каналов.')
        return

    text = '📋 <b>Список каналов:</b>\n\n'
    for channel in channels:
        text += f"🔹 {channel[1]} - {channel[2]}\n"

    await message.answer(text)

@dp.message_handler(lambda message: message.text == '📢 Рассылка' and message.from_user.id in ADMINS)
async def start_ras(message: types.Message):
    await message.answer('✉️ Введите сообщение для рассылки:')

@dp.message_handler(lambda message: message.reply_to_message and message.reply_to_message.text == '✉️ Введите сообщение для рассылки:' and message.from_user.id in ADMINS)
async def process_ras(message: types.Message):
    text = message.text
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users')
    users = cursor.fetchall()
    conn.close()

    success = 0
    fail = 0

    for user in users:
        try:
            telegram_id = user[0]
            await bot.send_message(telegram_id, text)
            success += 1
        except:
            fail += 1

    await message.answer(f"📢 Рассылка завершена:\n✅ Успешно: {success}\n❌ Не удалось: {fail}")

@dp.callback_query_handler(lambda query: query.data == 'check')
async def check_sub(query: types.CallbackQuery):
    await bot.send_message(query.from_user.id, "<b>Вы не подписались🚫</b>")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)