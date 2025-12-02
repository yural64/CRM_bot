"""
Модуль для работы с базой данных PostgreSQL (Neon).
CRM-система для управления клиентами, услугами и записями.
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional
from datetime import datetime

from config import get_db_connection_string


class Database:
    """Класс для работы с базой данных CRM."""
    
    def __init__(self):
        self.connection_string = get_db_connection_string()
        self._ensure_tables_exist()
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для безопасного подключения к БД."""
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            yield conn
        finally:
            if conn:
                conn.close()
    
    @contextmanager
    def get_cursor(self, dict_cursor: bool = True):
        """Контекстный менеджер для работы с курсором."""
        with self.get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
    
    def _ensure_tables_exist(self):
        """Создаёт таблицы, если их ещё нет."""
        with self.get_cursor() as cursor:
            # Таблица клиентов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    phone VARCHAR(50),
                    telegram_id BIGINT UNIQUE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица услуг
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    price DECIMAL(10, 2) NOT NULL,
                    duration_minutes INTEGER DEFAULT 60,
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица записей (appointments)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                    service_id INTEGER NOT NULL REFERENCES services(id),
                    appointment_datetime TIMESTAMP NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Индексы для оптимизации
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_clients_telegram 
                ON clients(telegram_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_appointments_client 
                ON appointments(client_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_appointments_datetime 
                ON appointments(appointment_datetime)
            """)
            
            print("✅ Таблицы базы данных готовы")
    
    # =========================================================================
    # Методы для работы с клиентами (clients)
    # =========================================================================
    
    def get_client_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        """Получает клиента по Telegram ID."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM clients WHERE telegram_id = %s",
                (telegram_id,)
            )
            return cursor.fetchone()
    
    def get_client_by_id(self, client_id: int) -> Optional[dict]:
        """Получает клиента по ID."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
            return cursor.fetchone()
    
    def add_client(self, name: str, phone: str, telegram_id: int, notes: str = None) -> int:
        """Добавляет нового клиента."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO clients (name, phone, telegram_id, notes)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (name, phone, telegram_id, notes)
            )
            result = cursor.fetchone()
            return result['id']
    
    def update_client(self, client_id: int, **kwargs) -> bool:
        """Обновляет данные клиента."""
        if not kwargs:
            return False
        
        set_clause = sql.SQL(', ').join(
            sql.SQL("{} = %s").format(sql.Identifier(key))
            for key in kwargs.keys()
        )
        values = list(kwargs.values()) + [client_id]
        
        query = sql.SQL("UPDATE clients SET {} WHERE id = %s").format(set_clause)
        
        with self.get_cursor() as cursor:
            cursor.execute(query, values)
            return cursor.rowcount > 0
    
    def get_all_clients(self, limit: int = 100) -> list[dict]:
        """Получает список всех клиентов."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM clients ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            return cursor.fetchall()
    
    # =========================================================================
    # Методы для работы с услугами (services)
    # =========================================================================
    
    def get_all_services(self, active_only: bool = True) -> list[dict]:
        """Получает список услуг."""
        with self.get_cursor() as cursor:
            if active_only:
                cursor.execute(
                    "SELECT * FROM services WHERE is_active = TRUE ORDER BY name"
                )
            else:
                cursor.execute("SELECT * FROM services ORDER BY name")
            return cursor.fetchall()
    
    def get_service_by_id(self, service_id: int) -> Optional[dict]:
        """Получает услугу по ID."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
            return cursor.fetchone()
    
    def add_service(self, name: str, price: float, duration_minutes: int = 60, 
                    description: str = None) -> int:
        """Добавляет новую услугу."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO services (name, price, duration_minutes, description)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (name, price, duration_minutes, description)
            )
            result = cursor.fetchone()
            return result['id']
    
    # =========================================================================
    # Методы для работы с записями (appointments)
    # =========================================================================
    
    def add_appointment(self, client_id: int, service_id: int, 
                       appointment_datetime: datetime, comment: str = None) -> int:
        """Создаёт новую запись."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO appointments 
                (client_id, service_id, appointment_datetime, comment)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (client_id, service_id, appointment_datetime, comment)
            )
            result = cursor.fetchone()
            return result['id']
    
    def get_client_appointments(self, client_id: int, 
                                status: str = None) -> list[dict]:
        """Получает записи клиента."""
        with self.get_cursor() as cursor:
            if status:
                cursor.execute(
                    """
                    SELECT a.*, s.name as service_name, s.price
                    FROM appointments a
                    JOIN services s ON a.service_id = s.id
                    WHERE a.client_id = %s AND a.status = %s
                    ORDER BY a.appointment_datetime DESC
                    """,
                    (client_id, status)
                )
            else:
                cursor.execute(
                    """
                    SELECT a.*, s.name as service_name, s.price
                    FROM appointments a
                    JOIN services s ON a.service_id = s.id
                    WHERE a.client_id = %s
                    ORDER BY a.appointment_datetime DESC
                    """,
                    (client_id,)
                )
            return cursor.fetchall()
    
    def update_appointment_status(self, appointment_id: int, status: str) -> bool:
        """Обновляет статус записи."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "UPDATE appointments SET status = %s WHERE id = %s",
                (status, appointment_id)
            )
            return cursor.rowcount > 0
    
    def cancel_appointment(self, appointment_id: int) -> bool:
        """Отменяет запись."""
        return self.update_appointment_status(appointment_id, 'cancelled')
    
    # =========================================================================
    # Статистика
    # =========================================================================
    
    def get_stats(self) -> dict:
        """Получает общую статистику."""
        with self.get_cursor() as cursor:
            # Количество клиентов
            cursor.execute("SELECT COUNT(*) as count FROM clients")
            clients_count = cursor.fetchone()['count']
            
            # Количество услуг
            cursor.execute("SELECT COUNT(*) as count FROM services WHERE is_active = TRUE")
            services_count = cursor.fetchone()['count']
            
            # Количество записей
            cursor.execute("SELECT COUNT(*) as count FROM appointments")
            appointments_count = cursor.fetchone()['count']
            
            # Записи по статусам
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM appointments 
                GROUP BY status
            """)
            appointments_by_status = {row['status']: row['count'] 
                                     for row in cursor.fetchall()}
            
            return {
                'clients_count': clients_count,
                'services_count': services_count,
                'appointments_count': appointments_count,
                'appointments_by_status': appointments_by_status
            }
    
    # =========================================================================
    # Вспомогательные методы
    # =========================================================================
    
    def test_connection(self) -> bool:
        """Проверяет подключение к базе данных."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            print(f"Ошибка подключения к БД: {e}")
            return False


# Глобальный экземпляр для использования в приложении
db = Database()

