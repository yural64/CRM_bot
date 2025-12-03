# 🗄 API базы данных

Документация по методам класса `Database` для работы с PostgreSQL.

## 📚 Содержание

- [Подключение](#подключение)
- [Клиенты (Clients)](#клиенты-clients)
- [Услуги (Services)](#услуги-services)
- [Записи (Appointments)](#записи-appointments)
- [Статистика](#статистика)

## Подключение

### `test_connection() -> bool`

Проверяет подключение к базе данных.

```python
if db.test_connection():
    print("Подключение успешно")
```

---

## Клиенты (Clients)

### `get_client_by_telegram_id(telegram_id: int) -> Optional[dict]`

Получает клиента по Telegram ID.

```python
client = db.get_client_by_telegram_id(123456789)
if client:
    print(f"Клиент: {client['name']}")
```

**Возвращает:**
```python
{
    'id': 1,
    'name': 'Иван Иванов',
    'phone': '+7 900 123-45-67',
    'telegram_id': 123456789,
    'notes': None,
    'created_at': datetime(2025, 1, 1, 12, 0, 0)
}
```

### `get_client_by_id(client_id: int) -> Optional[dict]`

Получает клиента по ID.

```python
client = db.get_client_by_id(1)
```

### `add_client(name: str, phone: str, telegram_id: int, notes: str = None) -> int`

Добавляет нового клиента.

```python
client_id = db.add_client(
    name="Иван Иванов",
    phone="+7 900 123-45-67",
    telegram_id=123456789,
    notes="VIP клиент"
)
print(f"Создан клиент ID: {client_id}")
```

### `update_client(client_id: int, **kwargs) -> bool`

Обновляет данные клиента.

```python
success = db.update_client(
    client_id=1,
    phone="+7 900 999-99-99",
    notes="Обновлённые заметки"
)
```

### `get_all_clients(limit: int = 100) -> list[dict]`

Получает список всех клиентов (по умолчанию последние 100).

```python
clients = db.get_all_clients(limit=50)
for client in clients:
    print(client['name'])
```

---

## Услуги (Services)

### `get_all_services(active_only: bool = True) -> list[dict]`

Получает список услуг.

```python
# Только активные услуги
services = db.get_all_services()

# Все услуги (включая неактивные)
all_services = db.get_all_services(active_only=False)
```

**Возвращает:**
```python
[
    {
        'id': 1,
        'name': 'Стрижка',
        'price': Decimal('1500.00'),
        'duration_minutes': 60,
        'description': 'Мужская или женская стрижка',
        'is_active': True,
        'created_at': datetime(2025, 1, 1, 10, 0, 0)
    },
    ...
]
```

### `get_service_by_id(service_id: int) -> Optional[dict]`

Получает услугу по ID.

```python
service = db.get_service_by_id(1)
print(f"{service['name']}: {service['price']} руб.")
```

### `add_service(name: str, price: float, duration_minutes: int = 60, description: str = None) -> int`

Добавляет новую услугу.

```python
service_id = db.add_service(
    name="Окрашивание",
    price=3000.00,
    duration_minutes=120,
    description="Окрашивание волос"
)
```

---

## Записи (Appointments)

### `add_appointment(client_id: int, service_id: int, appointment_datetime: datetime, comment: str = None) -> int`

Создаёт новую запись.

```python
from datetime import datetime

appointment_id = db.add_appointment(
    client_id=1,
    service_id=1,
    appointment_datetime=datetime(2025, 12, 15, 14, 30),
    comment="Клиент просил мастера Анну"
)
```

### `get_client_appointments(client_id: int, status: str = None) -> list[dict]`

Получает записи клиента.

```python
# Все записи клиента
appointments = db.get_client_appointments(client_id=1)

# Только активные
pending = db.get_client_appointments(client_id=1, status='pending')
```

**Возвращает:**
```python
[
    {
        'id': 1,
        'client_id': 1,
        'service_id': 1,
        'appointment_datetime': datetime(2025, 12, 15, 14, 30),
        'status': 'pending',
        'comment': 'Клиент просил мастера Анну',
        'created_at': datetime(2025, 12, 1, 10, 0, 0),
        'service_name': 'Стрижка',  # JOIN с services
        'price': Decimal('1500.00')
    },
    ...
]
```

### `update_appointment_status(appointment_id: int, status: str) -> bool`

Обновляет статус записи.

```python
# Подтвердить запись
db.update_appointment_status(appointment_id=1, status='confirmed')

# Завершить
db.update_appointment_status(appointment_id=1, status='completed')
```

**Доступные статусы:**
- `pending` — ожидает подтверждения
- `confirmed` — подтверждена
- `cancelled` — отменена
- `completed` — завершена

### `cancel_appointment(appointment_id: int) -> bool`

Отменяет запись (сокращение для `update_appointment_status`).

```python
success = db.cancel_appointment(appointment_id=1)
```

---

## Статистика

### `get_stats() -> dict`

Получает общую статистику системы.

```python
stats = db.get_stats()
print(f"Клиентов: {stats['clients_count']}")
print(f"Услуг: {stats['services_count']}")
print(f"Записей: {stats['appointments_count']}")
print(f"По статусам: {stats['appointments_by_status']}")
```

**Возвращает:**
```python
{
    'clients_count': 150,
    'services_count': 10,
    'appointments_count': 450,
    'appointments_by_status': {
        'pending': 25,
        'confirmed': 50,
        'completed': 350,
        'cancelled': 25
    }
}
```

---

## Примеры использования

### Полный цикл работы с клиентом

```python
from database import db
from datetime import datetime, timedelta

# 1. Регистрация клиента
client_id = db.add_client(
    name="Мария Петрова",
    phone="+7 900 555-55-55",
    telegram_id=987654321
)

# 2. Просмотр услуг
services = db.get_all_services()
for service in services:
    print(f"{service['name']}: {service['price']} руб.")

# 3. Создание записи
tomorrow = datetime.now() + timedelta(days=1)
appointment_time = tomorrow.replace(hour=14, minute=0, second=0)

appointment_id = db.add_appointment(
    client_id=client_id,
    service_id=services[0]['id'],
    appointment_datetime=appointment_time
)

# 4. Просмотр записей клиента
appointments = db.get_client_appointments(client_id)
for app in appointments:
    print(f"Запись #{app['id']}: {app['service_name']} - {app['appointment_datetime']}")

# 5. Подтверждение записи
db.update_appointment_status(appointment_id, 'confirmed')

# 6. После оказания услуги
db.update_appointment_status(appointment_id, 'completed')

# 7. Статистика
stats = db.get_stats()
print(f"Всего клиентов: {stats['clients_count']}")
```

### Поиск свободных записей

```python
from datetime import datetime, timedelta

def get_available_slots(service_id: int, date: datetime) -> list:
    """Получает свободные слоты на дату."""
    # Это пример - нужно реализовать в database.py
    # Здесь просто демонстрация логики
    
    all_slots = [
        datetime.combine(date, datetime.strptime(t, "%H:%M").time())
        for t in ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00"]
    ]
    
    # Получить занятые слоты из БД
    # busy_slots = db.get_busy_slots(service_id, date)
    # available = [s for s in all_slots if s not in busy_slots]
    
    return all_slots
```

---

## Контекстные менеджеры

Для прямых запросов используйте контекстные менеджеры:

### `get_connection()`

```python
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients")
    results = cursor.fetchall()
```

### `get_cursor(dict_cursor: bool = True)`

```python
with db.get_cursor() as cursor:
    cursor.execute("SELECT * FROM services WHERE price > %s", (1000,))
    expensive_services = cursor.fetchall()
```

---

## Обработка ошибок

Все методы могут выбросить исключения при ошибках БД:

```python
try:
    client_id = db.add_client(
        name="Test",
        phone="+7 900 111-11-11",
        telegram_id=111111111
    )
except Exception as e:
    print(f"Ошибка: {e}")
```

**Типичные ошибки:**
- `psycopg2.IntegrityError` — нарушение ограничений (например, дубликат telegram_id)
- `psycopg2.OperationalError` — ошибка подключения
- `psycopg2.ProgrammingError` — ошибка SQL-запроса

---

## SQL-схема таблиц

### clients
```sql
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    telegram_id BIGINT UNIQUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### services
```sql
CREATE TABLE services (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### appointments
```sql
CREATE TABLE appointments (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services(id),
    appointment_datetime TIMESTAMP NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

