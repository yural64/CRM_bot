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
            "🚗 <b>Автосервис «ПрофиСервис»</b>\n"
            "Мы заботимся о вашем автомобиле!\n\n"
            "🔧 Доступные команды:\n\n"
            "📝 /book — записаться на услугу\n"
            "📋 /my_appointments — мои записи\n"
            "📊 /services — услуги автосервиса\n"
            "👤 /profile — мой профиль\n"
            "❓ /help — справка"
        )
    else:
        text = (
            f"👋 Привет, {user_name}!\n\n"
            "🚗 Добро пожаловать в <b>Автосервис «ПрофиСервис»</b>!\n\n"
            "Я помогу вам записаться на:\n"
            "🔹 Техническое обслуживание\n"
            "🔹 Ремонт и диагностику\n"
            "🔹 Шиномонтаж\n"
            "🔹 Кузовные работы\n"
            "🔹 И многое другое!\n\n"
            "📝 Нажмите /register для регистрации"
        )
    
    bot.reply_to(message, text, parse_mode='HTML')


@bot.message_handler(commands=['help'])
def cmd_help(message: types.Message):
    """Обработчик команды /help."""
    text = (
        "📖 <b>Справка по боту автосервиса</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start — начать работу с ботом\n"
        "/register — регистрация в системе\n"
        "/book — записаться на услугу\n"
        "/my_appointments — просмотр моих записей\n"
        "/services — каталог услуг автосервиса\n"
        "/profile — мой профиль и статистика\n"
        "/cancel — отменить текущее действие\n"
        "/help — эта справка\n\n"
        "🚗 <b>Наши услуги:</b>\n"
        "• Техническое обслуживание (ТО)\n"
        "• Ремонт двигателя и ходовой части\n"
        "• Шиномонтаж и балансировка\n"
        "• Кузовные и покрасочные работы\n"
        "• Диагностика и электрика\n"
        "• И многое другое!\n\n"
        "📞 По вопросам звоните: +7 (900) 123-45-67"
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

def categorize_services(services):
    """Группирует услуги по категориям."""
    categories = {
        '🔧 ТО и диагностика': [],
        '🛢️ Масла и жидкости': [],
        '🛑 Тормозная система': [],
        '🔩 Ходовая часть': [],
        '📐 Сход-развал': [],
        '🚗 Шиномонтаж': [],
        '⚡ Электрика': [],
        '🔧 Двигатель': [],
        '💨 Выхлопная система': [],
        '❄️ Кондиционер': [],
        '🎨 Кузовные работы': [],
        '➕ Дополнительно': []
    }
    
    for service in services:
        name = service['name']
        if 'ТО' in name or 'Предпродажная' in name or 'диагностика' in name.lower() and 'двигател' in name.lower():
            categories['🔧 ТО и диагностика'].append(service)
        elif 'масла' in name or 'масло' in name or 'жидкост' in name.lower():
            categories['🛢️ Масла и жидкости'].append(service)
        elif 'тормоз' in name.lower():
            categories['🛑 Тормозная система'].append(service)
        elif any(word in name.lower() for word in ['амортизатор', 'стойк', 'рулев', 'шаров', 'сайлентблок']):
            categories['🔩 Ходовая часть'].append(service)
        elif 'развал' in name.lower() or 'схождение' in name.lower():
            categories['📐 Сход-развал'].append(service)
        elif 'шиномонтаж' in name.lower() or 'балансир' in name.lower() or 'прокол' in name.lower() or 'хранение' in name.lower():
            categories['🚗 Шиномонтаж'].append(service)
        elif any(word in name.lower() for word in ['аккумулятор', 'электрик', 'свеч', 'генератор', 'стартер']):
            categories['⚡ Электрика'].append(service)
        elif any(word in name.lower() for word in ['грм', 'фильтр']) or 'двигател' in name.lower():
            categories['🔧 Двигатель'].append(service)
        elif 'выхлоп' in name.lower() or 'глушител' in name.lower() or 'катализатор' in name.lower():
            categories['💨 Выхлопная система'].append(service)
        elif 'кондиционер' in name.lower():
            categories['❄️ Кондиционер'].append(service)
        elif any(word in name.lower() for word in ['кузов', 'покраска', 'полировка', 'рихтовка', 'стекло']):
            categories['🎨 Кузовные работы'].append(service)
        else:
            categories['➕ Дополнительно'].append(service)
    
    # Убираем пустые категории
    return {k: v for k, v in categories.items() if v}


@bot.message_handler(commands=['services'])
def cmd_services(message: types.Message):
    """Показывает категории услуг."""
    try:
        services = db.get_all_services()
        
        if not services:
            bot.reply_to(message, "⚠️ Пока нет доступных услуг")
            return
        
        # Группируем услуги по категориям
        categories = categorize_services(services)
        
        # Создаём клавиатуру с категориями
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        for category_name, category_services in categories.items():
            keyboard.add(
                types.InlineKeyboardButton(
                    f"{category_name} ({len(category_services)})",
                    callback_data=f"cat_{list(categories.keys()).index(category_name)}"
                )
            )
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚗  <b>УСЛУГИ АВТОСЕРВИСА</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 Всего услуг: <b>{len(services)}</b>\n"
            f"📁 Категорий: <b>{len(categories)}</b>\n\n"
            "Выберите категорию:"
        )
        
        bot.reply_to(message, text, parse_mode='HTML', reply_markup=keyboard)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def handle_category_selection(call: types.CallbackQuery):
    """Обработка выбора категории услуг."""
    try:
        # Получаем все услуги и категоризируем
        services = db.get_all_services()
        categories = categorize_services(services)
        category_names = list(categories.keys())
        
        # Получаем индекс выбранной категории
        category_index = int(call.data.split("_")[1])
        category_name = category_names[category_index]
        category_services = categories[category_name]
        
        bot.answer_callback_query(call.id)
        
        # Показываем услуги из категории (по 10 на странице)
        show_category_services(call.message, category_name, category_services, page=0)
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}")


def show_category_services(message, category_name, services, page=0):
    """Показывает услуги из выбранной категории с пагинацией."""
    services_per_page = 10
    start_idx = page * services_per_page
    end_idx = min(start_idx + services_per_page, len(services))
    services_page = services[start_idx:end_idx]
    
    # Формируем текст
    total_pages = (len(services) + services_per_page - 1) // services_per_page
    
    text = (
        "🚗 <b>УСЛУГИ АВТОСЕРВИСА</b>\n\n"
        f"📁 Категория: <b>{category_name}</b>\n"
        f"📊 Услуг в категории: <b>{len(services)}</b>\n\n"
    )
    
    for i, service in enumerate(services_page, start=start_idx + 1):
        text += (
            f"<b>{i}. {service['name']}</b>\n"
            f"   💰 {service['price']} руб. | ⏱ {service['duration_minutes']} мин.\n"
        )
        if service['description']:
            desc = service['description']
            if len(desc) > 100:
                desc = desc[:97] + "..."
            text += f"   📝 <i>{desc}</i>\n"
        text += "\n"
    
    if total_pages > 1:
        text += f"<i>Страница {page + 1} из {total_pages}</i>\n"
    
    text += "\n📝 Для записи используйте /book"
    
    # Создаём клавиатуру навигации
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    
    # Кнопка "Назад" (к предыдущей странице)
    if page > 0:
        # Получаем индекс категории для callback
        all_services = db.get_all_services()
        categories = categorize_services(all_services)
        category_index = list(categories.keys()).index(category_name)
        buttons.append(
            types.InlineKeyboardButton(
                "◀️ Назад",
                callback_data=f"catpage_{category_index}_{page - 1}"
            )
        )
    
    # Кнопка "К категориям"
    buttons.append(
        types.InlineKeyboardButton(
            "📁 Категории",
            callback_data="back_to_categories"
        )
    )
    
    # Кнопка "Далее" (к следующей странице)
    if end_idx < len(services):
        all_services = db.get_all_services()
        categories = categorize_services(all_services)
        category_index = list(categories.keys()).index(category_name)
        buttons.append(
            types.InlineKeyboardButton(
                "Далее ▶️",
                callback_data=f"catpage_{category_index}_{page + 1}"
            )
        )
    
    keyboard.add(*buttons)
    
    # Отправляем или редактируем сообщение
    try:
        bot.edit_message_text(
            text,
            message.chat.id,
            message.message_id,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    except:
        bot.send_message(
            message.chat.id,
            text,
            parse_mode='HTML',
            reply_markup=keyboard
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("catpage_"))
def handle_category_page(call: types.CallbackQuery):
    """Обработка пагинации внутри категории."""
    try:
        # Парсим callback_data: catpage_{category_index}_{page}
        parts = call.data.split("_")
        category_index = int(parts[1])
        page = int(parts[2])
        
        # Получаем категорию и её услуги
        services = db.get_all_services()
        categories = categorize_services(services)
        category_names = list(categories.keys())
        category_name = category_names[category_index]
        category_services = categories[category_name]
        
        bot.answer_callback_query(call.id)
        show_category_services(call.message, category_name, category_services, page=page)
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}")


@bot.callback_query_handler(func=lambda call: call.data == "back_to_categories")
def handle_back_to_categories(call: types.CallbackQuery):
    """Возврат к списку категорий."""
    try:
        services = db.get_all_services()
        categories = categorize_services(services)
        
        # Создаём клавиатуру с категориями
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        for category_name, category_services in categories.items():
            keyboard.add(
                types.InlineKeyboardButton(
                    f"{category_name} ({len(category_services)})",
                    callback_data=f"cat_{list(categories.keys()).index(category_name)}"
                )
            )
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚗  <b>УСЛУГИ АВТОСЕРВИСА</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 Всего услуг: <b>{len(services)}</b>\n"
            f"📁 Категорий: <b>{len(categories)}</b>\n\n"
            "Выберите категорию:"
        )
        
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}")


# =============================================================================
# Запись на услугу
# =============================================================================

@bot.message_handler(commands=['book'])
def cmd_book(message: types.Message):
    """Начало процесса записи - выбор категории."""
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
    
    # Группируем по категориям
    categories = categorize_services(services)
    
    # Создаём клавиатуру с категориями
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    for category_name, category_services in categories.items():
        keyboard.add(
            types.InlineKeyboardButton(
                f"{category_name} ({len(category_services)})",
                callback_data=f"book_cat_{list(categories.keys()).index(category_name)}"
            )
        )
    
    text = (
        "📝 <b>ЗАПИСЬ НА УСЛУГУ</b>\n\n"
        "Шаг 1️⃣: Выберите категорию услуги"
    )
    
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith("book_cat_"))
def handle_booking_category_selection(call: types.CallbackQuery):
    """Обработка выбора категории для записи."""
    try:
        # Получаем все услуги и категоризируем
        services = db.get_all_services()
        categories = categorize_services(services)
        category_names = list(categories.keys())
        
        # Получаем индекс выбранной категории
        category_index = int(call.data.split("_")[2])
        category_name = category_names[category_index]
        category_services = categories[category_name]
        
        bot.answer_callback_query(call.id)
        
        # Показываем услуги из категории для записи
        show_booking_services(call.message, category_name, category_services, category_index)
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}")


def show_booking_services(message, category_name, services, category_index):
    """Показывает услуги из категории для записи."""
    # Создаём клавиатуру с услугами
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for service in services:
        keyboard.add(
            types.InlineKeyboardButton(
                f"{service['name']} - {service['price']} руб.",
                callback_data=f"bookserv_{service['id']}"
            )
        )
    
    # Кнопка "Назад к категориям"
    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 К выбору категории",
            callback_data="back_to_booking_categories"
        )
    )
    
    text = (
        f"📝 <b>ЗАПИСЬ НА УСЛУГУ</b>\n\n"
        f"Категория: <b>{category_name}</b>\n"
        f"Шаг 2️⃣: Выберите услугу ({len(services)} доступно):"
    )
    
    # Отправляем или редактируем сообщение
    try:
        bot.edit_message_text(
            text,
            message.chat.id,
            message.message_id,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    except:
        bot.send_message(
            message.chat.id,
            text,
            parse_mode='HTML',
            reply_markup=keyboard
        )


@bot.callback_query_handler(func=lambda call: call.data == "back_to_booking_categories")
def handle_back_to_booking_categories(call: types.CallbackQuery):
    """Возврат к выбору категории при записи."""
    try:
        services = db.get_all_services()
        categories = categorize_services(services)
        
        # Создаём клавиатуру с категориями
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        for category_name, category_services in categories.items():
            keyboard.add(
                types.InlineKeyboardButton(
                    f"{category_name} ({len(category_services)})",
                    callback_data=f"book_cat_{list(categories.keys()).index(category_name)}"
                )
            )
        
        text = (
            "📝 <b>ЗАПИСЬ НА УСЛУГУ</b>\n\n"
            "Шаг 1️⃣: Выберите категорию услуги"
        )
        
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("bookserv_"))
def handle_service_selection(call: types.CallbackQuery):
    """Обработка выбора услуги для записи."""
    service_id = int(call.data.split("_")[1])
    service = db.get_service_by_id(service_id)
    
    if not service:
        bot.answer_callback_query(call.id, "❌ Услуга не найдена")
        return
    
    bot.answer_callback_query(call.id)
    
    # Создаём клавиатуру с датами
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    today = datetime.now()
    
    for i in range(7):  # Следующие 7 дней
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date.weekday()]
        
        # Передаём service_id в callback_data
        keyboard.add(
            types.InlineKeyboardButton(
                f"{weekday}, {date_str}",
                callback_data=f"bdate_{service_id}_{date.strftime('%Y-%m-%d')}"
            )
        )
    
    text = (
        f"📝 <b>ЗАПИСЬ НА УСЛУГУ</b>\n\n"
        f"✅ Услуга: <b>{service['name']}</b>\n"
        f"💰 Цена: <b>{service['price']} руб.</b>\n\n"
        f"Шаг 3️⃣: Выберите дату:"
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("bdate_"))
def handle_booking_date_selection(call: types.CallbackQuery):
    """Обработка выбора даты для записи."""
    # Парсим callback_data: bdate_{service_id}_{date}
    parts = call.data.split("_")
    service_id = int(parts[1])
    date_str = parts[2]
    
    bot.answer_callback_query(call.id)
    
    # Получаем информацию об услуге
    service = db.get_service_by_id(service_id)
    if not service:
        bot.answer_callback_query(call.id, "❌ Услуга не найдена")
        return
    
    # Создаём клавиатуру со временем
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    times = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
    
    for time in times:
        # Передаём service_id и дату в callback_data
        keyboard.add(
            types.InlineKeyboardButton(
                time,
                callback_data=f"btime_{service_id}_{date_str}_{time}"
            )
        )
    
    # Кнопка "Назад" с service_id
    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 Назад к датам",
            callback_data=f"backserv_{service_id}"
        )
    )
    
    text = (
        f"📝 <b>ЗАПИСЬ НА УСЛУГУ</b>\n\n"
        f"✅ Услуга: <b>{service['name']}</b>\n"
        f"💰 Цена: <b>{service['price']} руб.</b>\n"
        f"📅 Дата: <b>{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n\n"
        f"Шаг 4️⃣: Выберите время:"
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("backserv_"))
def handle_back_to_dates(call: types.CallbackQuery):
    """Возврат к выбору даты."""
    try:
        # Получаем service_id из callback_data
        service_id = int(call.data.split("_")[1])
        
        bot.answer_callback_query(call.id)
        
        service = db.get_service_by_id(service_id)
        if not service:
            bot.answer_callback_query(call.id, "❌ Услуга не найдена")
            return
        
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
                    callback_data=f"bdate_{service_id}_{date.strftime('%Y-%m-%d')}"
                )
            )
        
        text = (
            f"📝 <b>ЗАПИСЬ НА УСЛУГУ</b>\n\n"
            f"✅ Услуга: <b>{service['name']}</b>\n"
            f"💰 Цена: <b>{service['price']} руб.</b>\n\n"
            f"Шаг 3️⃣: Выберите дату:"
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("btime_"))
def handle_booking_time_selection(call: types.CallbackQuery):
    """Обработка выбора времени и создание записи."""
    try:
        # Парсим callback_data: btime_{service_id}_{date}_{time}
        parts = call.data.split("_")
        service_id = int(parts[1])
        date_str = parts[2]
        time_str = parts[3]
        
        bot.answer_callback_query(call.id, "⏳ Создаём запись...")
        
        # Получаем информацию об услуге
        service = db.get_service_by_id(service_id)
        if not service:
            bot.edit_message_text(
                "❌ Ошибка: услуга не найдена",
                call.message.chat.id,
                call.message.message_id
            )
            return
        
        # Собираем дату и время
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        date_display = date_obj.strftime('%d.%m.%Y')
        weekday = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"][date_obj.weekday()]
        datetime_str = f"{date_str} {time_str}"
        appointment_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        
        # Создаём запись
        client = db.get_client_by_telegram_id(call.from_user.id)
        
        if not client:
            bot.edit_message_text(
                "❌ Ошибка: клиент не найден. Пожалуйста, зарегистрируйтесь: /register",
                call.message.chat.id,
                call.message.message_id
            )
            return
        
        appointment_id = db.add_appointment(
            client_id=client['id'],
            service_id=service_id,
            appointment_datetime=appointment_datetime
        )
        
        # Успешное сообщение
        text = (
            "╔═══════════════════════╗\n"
            "║  ✅  <b>ЗАПИСЬ ПОДТВЕРЖДЕНА!</b>  ║\n"
            "╚═══════════════════════╝\n\n"
            f"👤 Клиент: <b>{client['name']}</b>\n"
            f"📱 Телефон: <b>{client['phone']}</b>\n\n"
            f"🔧 Услуга: <b>{service['name']}</b>\n"
            f"💰 Стоимость: <b>{service['price']} руб.</b>\n"
            f"⏱ Длительность: <b>{service['duration_minutes']} мин.</b>\n\n"
            f"📅 Дата: <b>{date_display}</b> ({weekday})\n"
            f"🕐 Время: <b>{time_str}</b>\n\n"
            f"📋 Номер записи: <b>#{appointment_id}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💼 <b>Автосервис «ПрофиСервис»</b>\n"
            "Мы ждём вас в указанное время! 🚗\n\n"
            "<i>За 1 день до визита мы отправим вам напоминание.</i>\n\n"
            "📋 /my_appointments — все мои записи\n"
            "📞 Контакты: +7 (900) 123-45-67"
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
        
        # Отправляем дополнительное сообщение с благодарностью
        thanks_message = (
            "🙏 <b>Спасибо за ваш выбор!</b>\n\n"
            "Мы заботимся о вашем автомобиле как о своём.\n"
            "Если возникнут вопросы — звоните!\n\n"
            "🔔 Напоминание придёт за день до визита."
        )
        bot.send_message(
            call.message.chat.id,
            thanks_message,
            parse_mode='HTML'
        )
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ <b>Ошибка создания записи</b>\n\n"
            f"Не удалось создать запись:\n"
            f"<code>{e}</code>\n\n"
            f"Пожалуйста, попробуйте снова или свяжитесь с нами:\n"
            f"📞 +7 (900) 123-45-67",
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
    print("=" * 70)
    print("🚗 Telegram-бот автосервиса «ПрофиСервис» запускается...")
    print("=" * 70)
    
    # Проверяем подключение к БД
    if db.test_connection():
        print("✅ Подключение к базе данных успешно")
        
        # Статистика
        stats = db.get_stats()
        print(f"\n📊 Текущая статистика:")
        print(f"   • Клиентов: {stats['clients_count']}")
        print(f"   • Услуг: {stats['services_count']}")
        print(f"   • Записей: {stats['appointments_count']}")
        
        if stats['services_count'] == 0:
            print("\n⚠️  ВНИМАНИЕ: В базе нет услуг!")
            print("   Запустите: python add_autoservice_services.py")
    else:
        print("❌ Не удалось подключиться к базе данных")
        print("   Проверьте настройки в файле .env")
        return
    
    print("\n" + "=" * 70)
    print("🚀 Бот запущен и готов к работе!")
    print("=" * 70 + "\n")
    
    # Запуск бота
    bot.infinity_polling(timeout=60, long_polling_timeout=60)


if __name__ == '__main__':
    main()

