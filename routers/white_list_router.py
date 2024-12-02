from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from shared.enums import EUserStatus
from .command_router import show_whitelist_menu, UserState
from shared.funcs import (
    extract_domain,
    users,
    update_white_list,
    update_applications_sent,
    get_start_keyboard,
)

from shared.config import (
    active_sending,
    active_sessions,
    logger,
    active_domains,
    active_tasks,
    user_request_counter,
)


from shared.keyboards import start_keyboard

white_list_router = Router()


# Додавання доменів до вайтлиста
@white_list_router.message(lambda message: message.text == "📌 Додати домен")
async def request_domain(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = users.get(user_id, {})
    user_domains = user_data.get("whitelist", [])

    # Перевірка статусу користувача
    if user_data.get("status") == EUserStatus.DEMO:
        return await message.answer(
            "❌ Ця функція доступна тільки у платній версії боту."
        )

    # Перевірка, чи користувач досяг ліміту на 7 домени
    if (
        user_data.get("status") == EUserStatus.UNLIMITED
        and len(user_domains) >= 7
        or user_data.get("status") == EUserStatus.MAX
        and len(user_domains) >= 7
    ):
        return await message.answer(
            "❌ Ви не можете додати більше 7-ми доменів.",
            reply_markup=get_start_keyboard(user_id),
        )

    await message.answer(
        "📩 Відправте посилання на сайт, домен якого ви хочете додати.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="↩️ Повернутися назад")],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    user_id = message.from_user.id

    user_state = await state.get_state()

    if (
        user_state == UserState.waiting_for_duration
        or user_state == UserState.waiting_for_frequency
    ):
        active_sessions[user_id].pop(-1)
        active_domains[user_id].pop(list(active_domains[user_id].keys())[-1])

    await state.set_state(UserState.waiting_for_domain)


# Функція для обробки натискання на кнопку "Список доменів"
@white_list_router.message(lambda message: message.text == "📃 Список доменів")
async def list_domains(message: Message, state: FSMContext, user_id=None):
    # Ініціалізуємо ідентифікатор користувача
    user_id = user_id or message.from_user.id
    user_domains = users.get(user_id, {}).get("whitelist", [])

    user_id = message.from_user.id

    user_state = await state.get_state()

    if (
        user_state == UserState.waiting_for_duration
        or user_state == UserState.waiting_for_frequency
    ):
        active_sessions[user_id].pop(-1)
        active_domains[user_id].pop(list(active_domains[user_id].keys())[-1])

    await state.set_state(UserState.domain_list)

    # Створюємо список кнопок
    domain_buttons = [[KeyboardButton(text=domain)] for domain in user_domains]
    domain_buttons.append([KeyboardButton(text="↩️ Повернутися назад")])

    domain_keyboard = ReplyKeyboardMarkup(
        keyboard=domain_buttons, resize_keyboard=True, one_time_keyboard=True
    )

    # Надсилаємо повідомлення залежно від наявності доменів
    if not user_domains:
        await message.answer(
            text="📋 Ваш вайтлист порожній.", reply_markup=domain_keyboard
        )
    else:
        await message.answer(
            text="Виберіть домен, який хочете видалити:", reply_markup=domain_keyboard
        )


# Функція для обробки натискання на домен в вайтлисті для видалення
@white_list_router.message(
    lambda message: message.text
    in [domain for domain in users.get(message.from_user.id, {}).get("whitelist", [])]
)
async def delete_domain(message: Message, state: FSMContext):
    user_id = message.from_user.id
    domain_to_remove = message.text

    # Видаляємо домен з вайтлиста
    if domain_to_remove in users[user_id].get("whitelist", []):
        users[user_id]["whitelist"].remove(domain_to_remove)

        white_list_str = ""
        for domain in users[user_id]["whitelist"]:
            white_list_str += f"{domain}, "
        update_white_list(user_id, white_list_str.strip().strip(","))

        # save_users(users)
        await message.answer(f"✅ Домен {domain_to_remove} видалено з вайтлиста.")
    else:
        await message.answer("❌ Домен не знайдено у вашому вайтлисті.")

    # Повертаємось до списку доменів
    await list_domains(message, state)


# Функція для обробки натискання на кнопку "Додати домен"
@white_list_router.message(UserState.waiting_for_domain)
async def add_domain(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_domain = message.text

    # Отримуємо домен з URL
    domain = extract_domain(user_domain)
    logger.info(f"Користувач {user_id} додав домен {domain} до вайтлиста")
    # Додаємо домен до користувача
    users[user_id]["whitelist"] = users[user_id].get("whitelist", [])
    if domain not in users[user_id]["whitelist"]:
        users[user_id]["whitelist"].append(domain)

        white_list_str = ""
        for url in users[user_id]["whitelist"]:
            white_list_str += f"{url}, "
        update_white_list(user_id, white_list_str.strip().strip(","))

        # save_users(users)  # Зберегти оновлення
        await message.answer(f"✅ Домен {domain} успішно додано до вайтлиста.")
        # Зупинка активних завдань із вказаним доменом
        logger.info(active_domains.items())
        for (
            user_id,
            url,
        ) in [
            (
                user_id,
                url,
            )
            for user_id, domain_url in active_domains.items()
            for domain_item, url in domain_url.items()
            if domain_item == domain
        ]:
            logger.info(
                f"Активна сесія користувача {user_id} із доменом {domain} з вайтлиста вилучена"
            )

            active_sessions[user_id].remove(url)
            task = active_tasks[user_id].pop(url)
            logger.info(f"Активне завдання користувача {user_id} відмінено")
            task.cancel()
            logger.info(f"{active_sessions[user_id]=}")

            count_requests = user_request_counter[user_id].pop(url)
            update_applications_sent(
                user_id, users[user_id]["applications_sent"] + count_requests
            )
            users[user_id]["applications_sent"] += count_requests
            # Повідомлення користувачам про зупинку завдання
            logger.info(
                f"Повідомляємо користувача {user_id} про завершення відправки заявок. Всього {count_requests}"
            )

            await message.bot.send_message(
                chat_id=user_id,
                text=f"❌ Відправка заявок на {active_domains[user_id][domain]} завершена через додавання домену у вайт-лист.\n"
                f"✉️ Всього відправлено заявок: {count_requests}",
                reply_markup=get_start_keyboard(user_id),
            )
            active_domains[user_id].pop(domain)
        # for u_id in active_domains.keys():
        #     if domain in active_domains[u_id].keys():

        #         await state.set_state(UserState.waiting_for_start)
        #         active_sending[u_id] = False
        #         for task in active_tasks.get(u_id, {}).values():
        #             task.cancel()

        #         task = active_tasks.pop(u_id, None)
        #         active_sessions.pop(u_id, None)
        #         total_requests = 0
        #         for count_requests in user_request_counter.get(u_id, {}).values():
        #             total_requests += count_requests
        #         user_request_counter.pop(u_id, None)

        #         # Оновлення загальної кількості заявок
        #         if u_id in users:
        #             update_applications_sent(
        #                 u_id, users[u_id]["applications_sent"] + total_requests
        #             )
        #             users[u_id]["applications_sent"] += total_requests

        #         await message.bot.send_message(
        #             chat_id=u_id,
        #             text=f"❌ Відправка заявок на {active_domains[u_id][domain]} завершена через додавання домену у вайт-лист.\n"
        #             f"✉️ Всього відправлено заявок: {total_requests}",
        #             reply_markup=get_start_keyboard(u_id),
        #         )

        #         active_domains[u_id].pop(domain)
    else:
        await message.answer("❌ Цей домен вже додано до вайтлиста.")

    # Повертаємося до меню вайтлиста
    await show_whitelist_menu(message, state)
