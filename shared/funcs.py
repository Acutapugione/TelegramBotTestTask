import os
import aiohttp
import random
import phonenumbers
import re
import json
import tldextract
from datetime import datetime
from urllib.parse import quote

import sqlite3

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from random_user_agent.user_agent import UserAgent
from random_user_agent.params import OperatingSystem, SoftwareType, Popularity

from .callbacks import ProxyEditingCallbackData
from .enums import EUserStatus
from .keyboards import (
    demo_duration_keyboard,
    admin_duration_keyboard,
    start_keyboard,
    admin_start_keyboard,
)
from .data import demo_names, unlim_names, admin_names, max_names, operators
from .config import (
    PROXIES_FILE,
    logger,
    COUNTRY_CODES,
    PROXY_PATTERN,
    URL_PATTERN,
    PROXY_ATTEMPTS,
)

# Параметри випадкових User Agents
software_types = [SoftwareType.WEB_BROWSER.value]
popularity = [Popularity.POPULAR.value]
operating_systems = [
    OperatingSystem.WINDOWS.value,
    OperatingSystem.LINUX.value,
    OperatingSystem.MAC.value,
]
user_agent_rotator = UserAgent(
    software_types=software_types,
    operating_systems=operating_systems,
    popularity=popularity,
    limit=50,
)


try:
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT,
            registration_date TEXT,
            status TEXT,
            applications_sent INT,
            white_list TEXT,
            due_to TEXT DEFAULT '-'
        )
    """
    )
    conn.commit()
    conn.close()

except Exception as e:
    print(e)


def update_user_status(user_id, status, due_to):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE users SET status=?, due_to=? WHERE user_id=?""",
        (status, due_to, user_id),
    )
    conn.commit()
    conn.close()


def update_white_list(user_id, white_list):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE users SET white_list=? WHERE user_id=?""", (white_list, user_id)
    )
    conn.commit()
    conn.close()


def update_applications_sent(user_id, applications_sent):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE users SET applications_sent=? WHERE user_id=?""",
        (applications_sent, user_id),
    )
    conn.commit()
    conn.close()


# Функція для визначення імені відповідно до статусу користувача
def generate_name(user_id):
    user_status = get_user_status(user_id)  # Отримуємо статус користувача

    # Якщо статус користувача не знайдений, використовуємо статус 'demo'
    if user_status is None:
        user_status = EUserStatus.DEMO

    if user_status == EUserStatus.DEMO:
        return random.choice(demo_names)
    elif user_status == EUserStatus.UNLIMITED:
        return random.choice(unlim_names)
    elif user_status == EUserStatus.MAX:
        return random.choice(max_names)
    elif user_status == EUserStatus.ADMIN:
        return random.choice(admin_names)
    else:
        # Якщо статус не вказаний або невідомий, використовується список для статусу demo
        return random.choice(demo_names)


# Функція для генерації українського номера телефону з кодом оператора
def generate_phone_number():
    operator_name = random.choice(list(operators.keys()))
    operator_code = random.choice(operators[operator_name])
    phone_number = phonenumbers.parse(
        f"+{COUNTRY_CODES['ua']}{operator_code}{random.randint(1000000, 9999999)}", None
    )
    return phonenumbers.format_number(
        phone_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
    )


# Функція для перевірки коректності URL
def is_valid_url(url):
    return re.match(URL_PATTERN, url) is not None


def get_user_status(user_id):
    users = load_users()
    user_data = users.get(user_id, {})
    if user_data:
        return user_data.get("status")
    return None


# Функція для визначення клавіатури
def get_start_keyboard(user_id):
    users = load_users()  # Завантажуємо дані користувачів
    if users.get(user_id, {}).get("status") == EUserStatus.ADMIN:
        return admin_start_keyboard
    return start_keyboard


def get_duration_keyboard(user_id):
    users = load_users()  # Завантажуємо дані користувачів
    if users.get(user_id, {}).get("status") == EUserStatus.ADMIN:
        return admin_duration_keyboard
    return demo_duration_keyboard


# Альтернативна асинхронна перевірка URL за допомогою aiohttp
async def is_valid_url_aiohttp(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return response.status == 200
    except aiohttp.ClientError:
        return False


# Завантаження даних користувачів з БД
def load_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 
            user_id,
            registration_date,
            status,
            applications_sent,
            white_list,
            due_to 
        FROM users"""
    )

    users = {}

    for (
        user_id,
        registration_date,
        status,
        applications_sent,
        white_list,
        due_to,
    ) in cursor.fetchall():
        users[user_id] = {
            "id": user_id,
            "registration_date": registration_date,
            "status": status,
            "due_to": due_to,
            "applications_sent": applications_sent,
        }

        if white_list is not None:
            users[user_id]["whitelist"] = [
                domain.strip() for domain in white_list.split(",")
            ]

    return users


# Ініціалізація користувачів
users = load_users()


# Додавання нового користувача
def register_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "id": user_id,
            "registration_date": str(datetime.now()),
            "status": EUserStatus.DEMO,
            "applications_sent": 0,
            "applications_per_url": {},
        }

        try:
            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()
            cursor.execute(
                """
                    INSERT INTO users (user_id, registration_date, status, applications_sent)
                    VALUES (?, ?, ?, ?)
                """,
                (user_id, str(datetime.now()), EUserStatus.DEMO, 0),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Error: {e}")
        finally:
            conn.close()


# Функція для отримання домену з URL
def extract_domain(url: str) -> str:
    if os.environ.get("OS", "") == "Windows_NT":
        # TODO Сюди б прокинути __DIR__ з main файлу. Але убомовимось на те, що запуск завжди буде відбуватись з файлу main.py
        custom_cache_extract = tldextract.TLDExtract(cache_dir="cache/")
        extracted = custom_cache_extract(url)
    else:
        extracted = tldextract.extract(url)

    domain = f"{extracted.domain}.{extracted.suffix}"
    return domain


# Функція для перевірки чи користувач досяг ліміту заявок
def is_demo_limit_reached(user_id):
    user_data = users.get(user_id, {})
    return (
        user_data.get("status") == EUserStatus.DEMO
        and user_data.get("applications_sent", 0) >= 50
    )


# Завантаження даних проксі у словник
def load_proxies():
    try:
        with open(PROXIES_FILE, "r") as file:
            proxies = json.load(file)
            # Перетворюємо об'єкт проксі на словник для зручного доступу за ім'ям
            return {name: proxy for name, proxy in proxies.get("proxies", {}).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# Завантаження даних проксі з json файлу
def open_proxy_json():
    try:
        with open(PROXIES_FILE, "r") as file:
            proxies = json.load(file)
            return proxies
    except (FileNotFoundError, json.JSONDecodeError):
        return {"proxies": {}}


def get_proxy_url(proxy_data: dict):
    url = f"http://{quote(proxy_data['login'])}:{quote(proxy_data['password'])}@{proxy_data['ip']}:{proxy_data['port']}"
    return url


# Функція для перевірки коректності введеного проксі
def is_valid_proxy(proxy):
    return re.match(PROXY_PATTERN, proxy) is not None


# Функція для генерації повідомлення про проксі з інформацією про його статус та налаштування.
def generate_proxy_message(proxy_id, proxy_data):
    status = "Ввімкнене" if proxy_data["use_proxy"] else "Вимкнене"
    return (
        f"Проксі {proxy_id}:\n"
        f"Статус: {status}\n"
        f"IP: {proxy_data['ip']}\n"
        f"Порт: {proxy_data['port']}\n"
        f"Логін: {proxy_data['login']}\n"
        f"Пароль: {proxy_data['password']}\n"
    )


# Функція для генерації інлайн-клавіатури для проксі з кнопками для управління статусом та редагуванням.
def generate_proxy_inline_keyboard(proxy_id, use_proxy):
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="Вимкнути" if use_proxy else "Ввімкнути",
            callback_data=ProxyEditingCallbackData(
                action="toggle", proxy_id=proxy_id
            ).pack(),
        ),
        InlineKeyboardButton(
            text="Редагувати",
            callback_data=ProxyEditingCallbackData(
                action="edit", proxy_id=proxy_id
            ).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="Видалити дані",
            callback_data=ProxyEditingCallbackData(
                action="delete_data", proxy_id=proxy_id
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Видалити проксі",
            callback_data=ProxyEditingCallbackData(
                action="delete_proxy", proxy_id=proxy_id
            ).pack(),
        )
    )
    return builder.as_markup()


# Функція для перевірки працездатності проксі за заданими параметрами.
async def is_proxy_working(
    ip,
    port,
    login,
    password,
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/87.0.4280.88 Safari/537.36",
):
    proxy_url = f"http://{quote(login)}:{quote(password)}@{ip}:{port}"
    url = "https://checkip.amazonaws.com"  # Тестовый URL для перевiрки проксi
    # url = 'https://ifconfig.me/ip'
    # url = 'https://httpbin.org/ip'

    timeout = aiohttp.ClientTimeout(total=15)

    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False), timeout=timeout
    ) as session:
        try:
            headers = {"User-Agent": user_agent}
            # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'

            async with session.get(url, proxy=proxy_url, headers=headers) as response:

                if response.status == 200:
                    return True
                else:
                    logger.error(f"Returned status {response.status} for {proxy_url}")
                    return False
        except aiohttp.ClientError as e:
            logger.error(f"Client error with proxy {proxy_url}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error with proxy {proxy_url}: {str(e)}")
            return False


async def check_proxy(proxy, user_agent, proxies):
    for attempt in range(PROXY_ATTEMPTS):
        if await is_proxy_working(
            ip=proxy["ip"],
            port=proxy["port"],
            login=proxy["login"],
            password=proxy["password"],
            user_agent=user_agent,
        ):
            proxies.append(get_proxy_url(proxy))
            return
        else:
            logger.error(
                f"Проксі http://{proxy['login']}:{proxy['password']}@{proxy['ip']}:{proxy['port']} недоступне, спроба {attempt+1} з {PROXY_ATTEMPTS}"
            )


# Функція для підготовки повідомлень про проксі з інформацією та інлайн-клавіатурами.
async def prepare_proxy_messages(proxies_dict: dict) -> list:
    proxy_messages = []
    for proxy_id, proxy_data in proxies_dict.items():
        text = generate_proxy_message(proxy_id, proxy_data)
        keyboard = generate_proxy_inline_keyboard(proxy_id, proxy_data["use_proxy"])
        proxy_messages.append((text, keyboard))
    return proxy_messages


# Функція для оновлення данных проксi
def update_proxy_data(proxy_id, ip, port, login, password, proxies=None):
    if proxies is None:
        proxies = open_proxy_json()

    if proxy_id in proxies["proxies"]:
        proxies["proxies"][proxy_id]["ip"] = ip
        proxies["proxies"][proxy_id]["port"] = port
        proxies["proxies"][proxy_id]["login"] = login
        proxies["proxies"][proxy_id]["password"] = password

        with open(PROXIES_FILE, "w") as file:
            json.dump(proxies, file, indent=4)


# Функція для створення нового проксі
def insert_proxy_data(ip, port, login, password):
    proxies = open_proxy_json()

    proxy_id = "1"

    for proxy_id_int in range(1, len(proxies["proxies"]) + 2):
        if str(proxy_id_int) not in proxies["proxies"]:
            proxy_id = str(proxy_id_int)
            break

    proxies["proxies"][proxy_id] = {}
    proxies["proxies"][proxy_id]["use_proxy"] = False

    update_proxy_data(proxy_id, ip, port, login, password, proxies)
    return proxy_id


# Функція для перемикання стану використання проксі за вказаним ідентифікатором.
def toggle_proxy_state(proxy_id):
    proxies = open_proxy_json()
    if proxy_id in proxies["proxies"]:
        current_state = proxies["proxies"][proxy_id]["use_proxy"]
        new_state = not current_state

        proxies["proxies"][proxy_id]["use_proxy"] = new_state
        with open(PROXIES_FILE, "w") as file:
            json.dump(proxies, file, indent=4)


# Функція видалення даних з проксі
def delete_proxy_data(proxy_id):
    proxies = open_proxy_json()
    if proxy_id in proxies["proxies"]:
        proxies["proxies"][proxy_id]["ip"] = ""
        proxies["proxies"][proxy_id]["port"] = ""
        proxies["proxies"][proxy_id]["login"] = ""
        proxies["proxies"][proxy_id]["password"] = ""
        proxies["proxies"][proxy_id]["type"] = ""

        with open(PROXIES_FILE, "w") as file:
            json.dump(proxies, file, indent=4)


# Функція видалення проксі та новий порядок
def delete_proxy(proxy_id):
    data = open_proxy_json()

    if proxy_id in data["proxies"]:
        del data["proxies"][proxy_id]

    proxies = data["proxies"]
    keys = list(proxies.keys())
    for i in range(len(keys)):
        new_key = str(i + 1)
        proxies[new_key] = proxies.pop(keys[i])

    with open("proxies.json", "w") as file:
        json.dump(data, file, indent=4)


# Функція отримання випадкового User Agent
def get_user_agent():
    return user_agent_rotator.get_random_user_agent()
