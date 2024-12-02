# Telegram Bot

## Залежності

- Python 3.10+
- [Poetry](https://python-poetry.org/) для управління залежностями

## Запуск бота

1. *Встановлення залежностей (тільки при першому запуску)*:

   ```bash
   poetry install
   ```
   
2. *Створення .env файлу та заповнення інформації*:

   ```bash
   cp .env.example .env
   ```

- Скопіюйте URL сервера для отримання оновлень від Telegram та додайте у `WEBHOOK_URL` у `.env`

3. *Активація робочого середовища*:

   ```bash
   poetry shell
   ```

4. *Запуск бота*:

   ```bash
   python main.py
   ```
   
### NOTE

За замовчуванням бот запуститься у режимі розробки (polling), для запуску в режимі **WebHook** Запустіть **Docker** контейнер, або змініть `DEVELOPMENT` на `False` у `.env`

```
DEVELOPMENT=False
``` 