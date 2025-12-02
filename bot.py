"""
CRM Telegram-бот для управления клиентами и записями на услуги.
"""

from datetime import datetime, timedelta
import re

import telebot
from telebot import types, custom_filters
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage

from config import BOT_TOKEN
from database import db


# Проверка наличия токена
if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN. Укажите его в файле .env")

# Инициализация хранилища состояний и бота
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(BOT_TOKEN, state_storage=state_storage)

# Регистрация фильтра состояний (обязательно для работы FSM!)
bot.add_custom_filter(custom_filters.StateFilter(bot))


# =============================================================================
# Состояния FSM
# =============================================================================

class ClientRegistration(StatesGroup):
    """Состояния для регистрации клиента."""
    waiting_for_name = State()
    waiting_for_phone = State()


class AppointmentBooking(StatesGroup):
    """Состояния для записи на услугу."""
    selecting_service = State()
    selecting_date = State()
    selecting_time = State()
    confirming = State()


# =============================================================================
# Команды
# =============================================================================

@bot.message_handler(commands=['start'])
def cmd_start(message: types.Message):
    """Обработчик команды /start."""
    user_name = message.from_user.first_name or "Пользователь"
    
    # Проверяем, зарегистрирован ли клиент
    client = db.get_client_by_telegram_id(message.from_user.id)
    
    if client:
        text = (
            f"👋 С возвращением, <b>{client['name']}</b>!\n\n"
            "🔧 Доступные команды:\n\n"
            "📝 /book — записаться на услугу\n"
            "📋 /my_appointments — мои записи\n"
            "📊 /services — посмотреть услуги\n"
            "👤 /profile — мой профиль\n"
            "❓ /help — справка"
        )
    else:
        text = (
            f"👋 Привет, {user_name}!\n\n"
            "Я CRM-бот для записи на услуги.\n"
            "Давай сначала зарегистрируемся!\n\n"
            "📝 Нажми /register для регистрации"
        )
    
    bot.reply_to(message, text, parse_mode='HTML')


@bot.message_handler(commands=['help'])
def cmd_help(message: types.Message):
    """Обработчик команды /help."""
    text = (
        "📖 <b>Доступные команды:</b>\n\n"
        "/start — начать работу\n"
        "/register — регистрация\n"
        "/book — записаться на услугу\n"
        "/my_appointments — мои записи\n"
        "/services — список услуг\n"
        "/profile — мой профиль\n"
        "/cancel — отменить действие\n"
        "/help — эта справка"
    )
    
    bot.reply_to(message, text, parse_mode='HTML')


@bot.message_handler(commands=['cancel'], state='*')
def cmd_cancel(message: types.Message):
    """Отмена текущего действия."""
    bot.delete_state(message.from_user.id, message.chat.id)
    bot.reply_to(message, "❌ Действие отменено.")


# =============================================================================
# Регистрация клиента
# =============================================================================

@bot.message_handler(commands=['register'])
def cmd_register(message: types.Message):
    """Начало регистрации клиента."""
    # Проверяем, не зарегистрирован ли уже
    client = db.get_client_by_telegram_id(message.from_user.id)
    if client:
        bot.reply_to(message, f"✅ Вы уже зарегистрированы как <b>{client['name']}</b>", parse_mode='HTML')
        return
    
    text = (
        "📝 <b>Регистрация</b>\n\n"
        "Как вас зовут?\n"
        "<i>(Введите ваше имя или ФИО)</i>"
    )
    
    bot.set_state(message.from_user.id, ClientRegistration.waiting_for_name, message.chat.id)
    bot.reply_to(message, text, parse_mode='HTML')


@bot.message_handler(state=ClientRegistration.waiting_for_name)
def process_name(message: types.Message):
    """Обработка ввода имени."""
    name = message.text.strip()
    
    if len(name) < 2:
        bot.reply_to(message, "⚠️ Имя слишком короткое. Попробуйте ещё раз.")
        return
    
    # Сохраняем имя
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['name'] = name
    
    # Переходим к вводу телефона
    bot.set_state(message.from_user.id, ClientRegistration.waiting_for_phone, message.chat.id)
    
    text = (
        f"✅ Отлично, <b>{name}</b>!\n\n"
        "📱 Введите ваш номер телефона\n"
        "<i>(Например: +7 (900) 123-45-67)</i>"
    )
    
    bot.reply_to(message, text, parse_mode='HTML')


@bot.message_handler(state=ClientRegistration.waiting_for_phone)
def process_phone(message: types.Message):
    """Обработка ввода телефона."""
    phone = message.text.strip()
    
    # Простая валидация
    if len(phone) < 10:
        bot.reply_to(message, "⚠️ Номер телефона слишком короткий. Попробуйте ещё раз.")
        return
    
    # Сохраняем клиента в БД
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        try:
            client_id = db.add_client(
                name=data['name'],
                phone=phone,
                telegram_id=message.from_user.id
            )
            
            text = (
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "✅  <b>РЕГИСТРАЦИЯ ЗАВЕРШЕНА!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 Имя: <b>{data['name']}</b>\n"
                f"📱 Телефон: <b>{phone}</b>\n\n"
                "Теперь вы можете записаться на услугу!\n\n"
                "📝 /book — записаться\n"
                "📊 /services — посмотреть услуги"
            )
            
            bot.reply_to(message, text, parse_mode='HTML')
            
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка регистрации:\n<code>{e}</code>", parse_mode='HTML')
    
    # Сбрасываем состояние
    bot.delete_state(message.from_user.id, message.chat.id)


# =============================================================================
# Просмотр услуг
# =============================================================================

@bot.message_handler(commands=['services'])
def cmd_services(message: types.Message):
    """Показывает список услуг."""
    try:
        services = db.get_all_services()
        
        if not services:
            bot.reply_to(message, "⚠️ Пока нет доступных услуг")
            return
        
        text = "━━━━━━━━━━━━━━━━━━━━━━\n📊  <b>НАШИ УСЛУГИ</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for service in services:
            text += (
                f"🔹 <b>{service['name']}</b>\n"
                f"   💰 Цена: {service['price']} руб.\n"
                f"   ⏱ Длительность: {service['duration_minutes']} мин.\n"
            )
            if service['description']:
                text += f"   📝 {service['description']}\n"
            text += "\n"
        
        text += "📝 Для записи используйте /book"
        
        bot.reply_to(message, text, parse_mode='HTML')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


# =============================================================================
# Запись на услугу
# =============================================================================

@bot.message_handler(commands=['book'])
def cmd_book(message: types.Message):
    """Начало процесса записи."""
    # Проверяем регистрацию
    client = db.get_client_by_telegram_id(message.from_user.id)
    if not client:
        bot.reply_to(message, "⚠️ Сначала зарегистрируйтесь: /register")
        return
    
    # Получаем услуги
    services = db.get_all_services()
    if not services:
        bot.reply_to(message, "⚠️ Пока нет доступных услуг")
        return
    
    # Создаём inline-клавиатуру с услугами
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for service in services:
        keyboard.add(
            types.InlineKeyboardButton(
                f"{service['name']} - {service['price']} руб.",
                callback_data=f"service_{service['id']}"
            )
        )
    
    text = (
        "📝 <b>Запись на услугу</b>\n\n"
        "Выберите услугу:"
    )
    
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith("service_"))
def handle_service_selection(call: types.CallbackQuery):
    """Обработка выбора услуги."""
    service_id = int(call.data.split("_")[1])
    service = db.get_service_by_id(service_id)
    
    if not service:
        bot.answer_callback_query(call.id, "❌ Услуга не найдена")
        return
    
    bot.answer_callback_query(call.id)
    
    # Сохраняем выбранную услугу
    with bot.retrieve_data(call.from_user.id, call.message.chat.id) as data:
        data['service_id'] = service_id
        data['service_name'] = service['name']
        data['service_price'] = float(service['price'])
    
    # Создаём клавиатуру с датами
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    today = datetime.now()
    
    for i in range(7):  # Следующие 7 дней
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date.weekday()]
        
        keyboard.add(
            types.InlineKeyboardButton(
                f"{weekday}, {date_str}",
                callback_data=f"date_{date.strftime('%Y-%m-%d')}"
            )
        )
    
    text = (
        f"✅ Услуга: <b>{service['name']}</b>\n"
        f"💰 Цена: <b>{service['price']} руб.</b>\n\n"
        "📅 Выберите дату:"
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def handle_date_selection(call: types.CallbackQuery):
    """Обработка выбора даты."""
    date_str = call.data.split("_")[1]
    
    bot.answer_callback_query(call.id)
    
    # Сохраняем дату
    with bot.retrieve_data(call.from_user.id, call.message.chat.id) as data:
        data['appointment_date'] = date_str
    
    # Создаём клавиатуру со временем
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    times = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
    
    for time in times:
        keyboard.add(
            types.InlineKeyboardButton(
                time,
                callback_data=f"time_{time}"
            )
        )
    
    keyboard.add(types.InlineKeyboardButton("🔙 Назад к датам", callback_data="back_to_dates"))
    
    text = (
        f"📅 Дата: <b>{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n\n"
        "🕐 Выберите время:"
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("time_"))
def handle_time_selection(call: types.CallbackQuery):
    """Обработка выбора времени."""
    time_str = call.data.split("_")[1]
    
    bot.answer_callback_query(call.id)
    
    # Сохраняем время
    with bot.retrieve_data(call.from_user.id, call.message.chat.id) as data:
        data['appointment_time'] = time_str
        
        # Собираем подтверждение
        date_str = data['appointment_date']
        date_display = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
        datetime_str = f"{date_str} {time_str}"
        appointment_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        
        # Создаём запись
        client = db.get_client_by_telegram_id(call.from_user.id)
        
        try:
            appointment_id = db.add_appointment(
                client_id=client['id'],
                service_id=data['service_id'],
                appointment_datetime=appointment_datetime
            )
            
            text = (
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "✅  <b>ЗАПИСЬ СОЗДАНА!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔹 Услуга: <b>{data['service_name']}</b>\n"
                f"💰 Цена: <b>{data['service_price']} руб.</b>\n"
                f"📅 Дата: <b>{date_display}</b>\n"
                f"🕐 Время: <b>{time_str}</b>\n\n"
                f"📋 Номер записи: <b>#{appointment_id}</b>\n\n"
                "Мы ждём вас! 🎉\n\n"
                "📋 /my_appointments — посмотреть записи"
            )
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
            
        except Exception as e:
            bot.edit_message_text(
                f"❌ Ошибка создания записи:\n<code>{e}</code>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )


# =============================================================================
# Мои записи
# =============================================================================

@bot.message_handler(commands=['my_appointments'])
def cmd_my_appointments(message: types.Message):
    """Показывает записи пользователя."""
    client = db.get_client_by_telegram_id(message.from_user.id)
    if not client:
        bot.reply_to(message, "⚠️ Сначала зарегистрируйтесь: /register")
        return
    
    appointments = db.get_client_appointments(client['id'])
    
    if not appointments:
        bot.reply_to(message, "📋 У вас пока нет записей\n\n📝 /book — записаться")
        return
    
    text = "━━━━━━━━━━━━━━━━━━━━━━\n📋  <b>МОИ ЗАПИСИ</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for app in appointments:
        status_emoji = {
            'pending': '🕐',
            'confirmed': '✅',
            'cancelled': '❌',
            'completed': '✔️'
        }.get(app['status'], '❓')
        
        dt = app['appointment_datetime']
        date_str = dt.strftime('%d.%m.%Y %H:%M')
        
        text += (
            f"{status_emoji} <b>#{app['id']}</b>\n"
            f"   🔹 {app['service_name']}\n"
            f"   📅 {date_str}\n"
            f"   💰 {app['price']} руб.\n"
            f"   Статус: {app['status']}\n\n"
        )
    
    bot.reply_to(message, text, parse_mode='HTML')


# =============================================================================
# Профиль
# =============================================================================

@bot.message_handler(commands=['profile'])
def cmd_profile(message: types.Message):
    """Показывает профиль пользователя."""
    client = db.get_client_by_telegram_id(message.from_user.id)
    if not client:
        bot.reply_to(message, "⚠️ Сначала зарегистрируйтесь: /register")
        return
    
    # Статистика записей
    appointments = db.get_client_appointments(client['id'])
    completed = len([a for a in appointments if a['status'] == 'completed'])
    
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👤  <b>МОЙ ПРОФИЛЬ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Имя: <b>{client['name']}</b>\n"
        f"Телефон: <b>{client['phone']}</b>\n"
        f"Записей: <b>{len(appointments)}</b>\n"
        f"Завершено: <b>{completed}</b>\n\n"
        f"Клиент с: {client['created_at'].strftime('%d.%m.%Y')}"
    )
    
    bot.reply_to(message, text, parse_mode='HTML')


# =============================================================================
# Обработка неизвестных сообщений
# =============================================================================

@bot.message_handler(func=lambda message: True, state=None)
def handle_unknown(message: types.Message):
    """Обработчик неизвестных сообщений."""
    text = (
        "🤔 Не понимаю эту команду.\n"
        "Используйте /help для просмотра команд."
    )
    
    bot.reply_to(message, text)


# =============================================================================
# Запуск бота
# =============================================================================

def main():
    """Точка входа в приложение."""
    print("🤖 CRM-бот запускается...")
    
    # Проверяем подключение к БД
    if db.test_connection():
        print("✅ Подключение к базе данных успешно")
        
        # Статистика
        stats = db.get_stats()
        print(f"📊 Клиентов: {stats['clients_count']}")
        print(f"📊 Услуг: {stats['services_count']}")
        print(f"📊 Записей: {stats['appointments_count']}")
    else:
        print("⚠️ Не удалось подключиться к базе данных")
    
    print("🚀 Бот запущен и готов к работе!")
    
    # Запуск бота
    bot.infinity_polling(timeout=60, long_polling_timeout=60)


if __name__ == '__main__':
    main()

