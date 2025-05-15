import logging

import httpx
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode

logger = logging.getLogger(__name__)


class BotUtils:
    def __init__(self, bot_instance: Bot, backend_url: str):
        self.bot = bot_instance
        self.backend_url = backend_url
        self.http_client = httpx.AsyncClient()
        self.sort_states = {}

    def generate_keyboard(self, list_id: str, item_list: list, completed: bool, owner_id: int, user_id: int,
                          current_page: int = 1, sorted_items=False) -> InlineKeyboardMarkup:
        if sorted_items:
            item_list = sorted(item_list, key=lambda x: x["name"].lower())

        buttons = []
        items_per_page = 6
        total_items = len(item_list)
        total_pages = (total_items + items_per_page - 1) // items_per_page if total_items > 0 else 0

        if total_items > items_per_page and not completed:
            start = (current_page - 1) * items_per_page
            end = min(start + items_per_page, total_items)
            page_items = item_list[start:end]
        else:
            page_items = item_list

        start_number = (current_page - 1) * items_per_page + 1

        for index, item in enumerate(page_items):
            item_id = item["item_id"]
            name = item["name"]
            bought = item["bought"]
            status_emoji = "🟩" if bought else "⬜️"
            item_number = f"{start_number + index}. "
            buttons.append([InlineKeyboardButton(text=f"{item_number}{name[:57]}{'...' if len(name) > 57 else ''}",
                                                 callback_data=f"none_{list_id}_{item_id}_{current_page}"),
                InlineKeyboardButton(text=status_emoji, callback_data=f"toggle_{list_id}_{item_id}_{current_page}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"delete_{list_id}_{item_id}_{current_page}")])

        if total_items > items_per_page and not completed:
            prev_button = (InlineKeyboardButton(text="⬅️",
                                                callback_data=f"prev_{list_id}_{current_page}") if current_page > 1 else InlineKeyboardButton(
                text="⬅️", callback_data="disabled_prev"))
            page_button = InlineKeyboardButton(text=f"{current_page}/{total_pages}",
                callback_data=f"page_{list_id}_{current_page}")
            next_button = (InlineKeyboardButton(text="➡️",
                                                callback_data=f"next_{list_id}_{current_page}") if current_page < total_pages else InlineKeyboardButton(
                text="➡️", callback_data="disabled_next"))
            buttons.append([prev_button, page_button, next_button])

        if not completed and item_list:
            if sorted_items == True:
                buttons.append(
                    [InlineKeyboardButton(text="Сортировка ✅", callback_data=f"sort_list_{list_id}_{current_page}")])
                buttons.append([InlineKeyboardButton(text="Поделиться", callback_data=f"share_{list_id}")])
            elif sorted_items == False:
                buttons.append(
                    [InlineKeyboardButton(text="Сортировка ❌", callback_data=f"sort_list_{list_id}_{current_page}")])
                buttons.append([InlineKeyboardButton(text="Поделиться", callback_data=f"share_{list_id}")])
        if not completed and user_id != owner_id:
            buttons.append([InlineKeyboardButton(text="Отписаться", callback_data=f"unsubscribe_{list_id}")])

        if not completed and total_items > 0 and user_id == owner_id:
            buttons.append([InlineKeyboardButton(text="Завершить", callback_data=f"complete_{list_id}")])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def generate_confirm_keyboard(self, list_id: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data=f"confirm_complete_{list_id}"),
             InlineKeyboardButton(text="Нет", callback_data=f"cancel_complete_{list_id}")]])

    async def close_client(self):
        await self.http_client.aclose()

    async def extract_id_and_send_typing(self, message):
        user_id = message.from_user.id
        username = message.from_user.username
        if username is None:
            await message.answer(
                "Извините, для использования бота <b>сделайте ваш username видимым</b> в настройках Telegram.")
            return None
        return user_id

    async def complete_list(self, user_id: int, list_id: str):
        try:
            response = await self.http_client.get(f"{self.backend_url}/lists/{list_id}/", timeout=10)
            response.raise_for_status()
            list_data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Ошибка получения данных списка: {e}")
            return

        if list_data["owner_id"] != user_id:
            return

        try:
            response = await self.http_client.post(f"{self.backend_url}/lists/{list_id}/complete/", timeout=10)
            response.raise_for_status()
            completion_data = response.json()
            users = completion_data.get("users", [])
            items = completion_data.get("items", [])
            last_message_ids_for_users = completion_data.get("last_message_ids_for_users", {})
        except httpx.HTTPError as e:
            logger.error(f"Ошибка завершения списка: {e}")
            return

        text = f"Список <b>завершен!</b>\n" + ("\n".join(
            f"{'🟩' if item['bought'] else '⬜️'} {item['name']}" for item in items) or "Список <b>был пуст</b>")

        for uid in users:
            try:
                response = await self.http_client.get(f"{self.backend_url}/users/{uid}/", timeout=10)
                response.raise_for_status()
                user_data = response.json()
                chat_id = user_data.get("chat_id")
            except httpx.HTTPError as e:
                logger.warning(f"Ошибка получения данных пользователя: {e}")
                chat_id = None

            if not chat_id:
                logger.warning(f"Chat_id для пользователя {uid} не найден.")
                continue

            last_message_ids = last_message_ids_for_users.get(str(uid), [])
            if last_message_ids:
                for msg_id in last_message_ids:
                    try:
                        await self.bot.delete_message(chat_id, msg_id)
                    except Exception as e:
                        logger.error(f"Не удалось удалить сообщение {msg_id} для пользователя {uid}: {e}")

            try:
                await self.bot.send_message(chat_id, text)
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение пользователю {uid}: {e}")

        try:
            for uid in users:
                try:
                    await self.http_client.post(f"{self.backend_url}/users/{uid}/clear_last_subscribed_list/",
                                                json={"list_id": list_id}, timeout=10)
                except httpx.HTTPError as e:
                    logger.warning(f"Ошибка очистки last_subscribed_list_id для пользователя {uid}: {e}")
        except Exception as e:
            logger.error(f"Общая ошибка при очистке last_subscribed_list_id после завершения списка: {e}")

    async def update_shopping_list_message(self, chat_id: int, user_id: int, list_id: str, current_page: int = None,
                                           notification_text: str = None):
        logger.debug(
            f"START update_shopping_list_message: chat_id={chat_id}, user_id={user_id}, list_id={list_id}, current_page={current_page}")

        if current_page is None:
            try:
                response = await self.http_client.get(
                    f"{self.backend_url}/utils/{user_id}/lists/{list_id}/current_page/", timeout=10)
                response.raise_for_status()
                current_page_data = response.json()
                current_page = current_page_data.get("current_page", 1)
            except httpx.HTTPError as e:
                logger.error(f"Ошибка получения текущей страницы: {e}")
                current_page = 1

        try:
            response = await self.http_client.get(f"{self.backend_url}/lists/{list_id}/", timeout=10)
            response.raise_for_status()
            list_data = response.json()
            last_notification_text = list_data.get("last_notification_text")
        except httpx.HTTPError as e:
            logger.warning(f"Ошибка получения списка {list_id}: {e}")
            return

        if not list_data:
            logger.warning(f"Список {list_id} не найден.")
            return

        item_list = list_data.get("items", [])
        completed = list_data.get("completed", False)
        owner_id = list_data.get("owner_id")

        owner_username = "<b>Неизвестный</b> владелец"
        try:
            owner_response = await self.http_client.get(f"{self.backend_url}/users/{owner_id}/", timeout=10)
            owner_response.raise_for_status()
            owner_data = owner_response.json()
            owner_username = owner_data.get("username", "Неизвестный владелец") or f"ID владельца: {owner_id}"
        except httpx.HTTPError as e:
            logger.error(f"Ошибка получения имени владельца: {e}")

        sorted_items_state = self.sort_states.get(list_id, False)
        if sorted_items_state:
            item_list = sorted(item_list, key=lambda x: x["name"].lower())
        total_items = len(item_list)
        items_per_page = 6
        total_pages = (total_items + items_per_page - 1) // items_per_page if total_items > 0 else 0

        current_page = max(1, min(current_page, total_pages)) if total_pages > 0 else 1

        text_prefix = f"{' [Завершен]' if completed else ''}\nВладелец списка: @{owner_username}\n"

        if notification_text:
            text_prefix += f"{notification_text}\n"
        elif last_notification_text:
            text_prefix += f"{last_notification_text}\n"

        items_text = "Ваш список пока пуст. Чтобы добавить покупки, просто отправьте мне сообщение с названиями покупок." if not item_list else (
                "<blockquote expandable=\"true\">" + "\n".join([
            f"{index + 1}. {'🟩' if item['bought'] else '⬜️'} {item['name'][:200]}{'' if len(item['name']) <= 200 else '...'}"
            for index, item in enumerate(item_list)]) + "</blockquote>")

        all_bought = total_items > 0 and all(item["bought"] for item in item_list)
        try:
            response = await self.http_client.get(f"{self.backend_url}/utils/{user_id}/lists/{list_id}/skip_confirm/",
                timeout=10)
            response.raise_for_status()
            skip_confirm = response.json().get("skip_confirm", False)
        except httpx.HTTPError as e:
            logger.error(f"Ошибка получения skip_confirm: {e}")
            skip_confirm = False

        text_suffix = "\n\n<b>Все элементы отмечены</b>. Завершить список?" if not completed and all_bought and not skip_confirm and owner_id == user_id else ""
        keyboard = self.generate_confirm_keyboard(list_id) if text_suffix else self.generate_keyboard(list_id,
                                                                                                      item_list,
                                                                                                      completed,
                                                                                                      owner_id, user_id,
                                                                                                      current_page,
                                                                                                      sorted_items=sorted_items_state)
        final_text = text_prefix + items_text + text_suffix

        try:
            response = await self.http_client.get(f"{self.backend_url}/utils/{user_id}/lists/{list_id}/last_message/",
                                                  timeout=10)
            response.raise_for_status()
            last_message_ids = response.json().get("last_message_ids", [])
        except httpx.HTTPError as e:
            logger.error(f"Ошибка получения ID последнего сообщения: {e}")
            last_message_ids = []

        if last_message_ids:
            msg_id_to_edit = last_message_ids[0]
            try:
                await self.bot.edit_message_text(chat_id=chat_id, message_id=msg_id_to_edit, text=final_text,
                    reply_markup=keyboard, parse_mode=ParseMode.HTML)
            except Exception as e:
                error_str = str(e)
                logger.error(f"Не удалось отредактировать сообщение {msg_id_to_edit}: {error_str}")
                try:
                    await self.bot.delete_message(chat_id, msg_id_to_edit)
                except Exception as e_del:
                    if "message to delete not found" in str(e_del):
                        logger.warning(f"Сообщение {msg_id_to_edit} для удаления не найдено, вероятно, уже удалено.")
                    else:
                        logger.error(f"Не удалось удалить сообщение {msg_id_to_edit}: {e_del}")
                try:
                    await self.http_client.delete(
                        f"{self.backend_url}/utils/{user_id}/lists/{list_id}/last_message/{msg_id_to_edit}/delete_one/",
                        timeout=10)
                    logger.info(
                        f"Устаревший last_message_id {msg_id_to_edit} очищен для user_id={user_id}, list_id={list_id}.")
                except httpx.HTTPError as e_delete_one:
                    logger.error(f"Не удалось удалить last_message_id {msg_id_to_edit} из бэкенда: {e_delete_one}")

                msg = await self.bot.send_message(chat_id, final_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
                await self.http_client.post(f"{self.backend_url}/utils/{user_id}/lists/{list_id}/last_message/",
                                            json={"message_id": msg.message_id}, timeout=10)
        else:
            msg = await self.bot.send_message(chat_id, final_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            await self.http_client.post(f"{self.backend_url}/utils/{user_id}/lists/{list_id}/last_message/",
                                        json={"message_id": msg.message_id}, timeout=10)

        if notification_text:
            try:
                await self.http_client.post(f"{self.backend_url}/lists/{list_id}/clear_notification/", timeout=10)
            except httpx.HTTPError as e:
                logger.error(f"Ошибка очистки уведомления на бэкенде: {e}")

        try:
            await self.http_client.post(f"{self.backend_url}/utils/{user_id}/lists/{list_id}/current_page/",
                                        json={"page": current_page}, timeout=10)
        except httpx.HTTPError as e:
            logger.error(f"Ошибка сохранения текущей страницы: {e}")

        logger.debug("END update_shopping_list_message: Завершено.")

    async def notify_list_change(self, list_id: str, exclude_user_id: int = None, action_type: str = None,
                                 item_name: str = None):
        try:
            response = await self.http_client.get(f"{self.backend_url}/lists/{list_id}/", timeout=10)
            response.raise_for_status()
            list_data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Ошибка получения списка {list_id}: {e}")
            return

        if not list_data:
            return
        logger.info(list_data)
        owner_id = list_data.get("owner_id")

        notification_text_to_store = None

        for user_id in list_data["users"]:
            logger.info(user_id)
            try:
                response = await self.http_client.get(f"{self.backend_url}/users/{user_id}/", timeout=10)
                response.raise_for_status()
                user_data = response.json()
                logger.info(user_data)
                chat_id = user_data.get("chat_id")
                username = user_data.get("username")

                if exclude_user_id == user_id:
                    username2_for_notification = username
                else:
                    response_user2 = await self.http_client.get(f"{self.backend_url}/users/{exclude_user_id}/",
                                                                timeout=10)
                    response_user2.raise_for_status()
                    user_data2 = response_user2.json()
                    username2_for_notification = user_data2.get("username")

                if exclude_user_id:
                    notification_text = ""
                    if action_type and item_name:
                        if action_type == "add":
                            notification_text = f"@{username2_for_notification or 'Пользователь'} <b>добавил(а)</b> в список: <i>{item_name}</i>"
                        elif action_type == "delete":
                            notification_text = f"@{username2_for_notification or 'Пользователь'} <b>удалил(а)</b> из списка: <i>{item_name}</i>"
                        elif action_type == "toggle":
                            notification_text = f"@{username2_for_notification or 'Пользователь'} <b>изменил(а) статус</b> элемента: <i>{item_name}</i>"
                        notification_text_to_store = notification_text

                    elif action_type == "unsubscribe":
                        notification_text_to_store = f"@{username2_for_notification or 'Пользователь'} <b>отписался(лась)</b> от списка."

                if action_type == "unsubscribe":
                    try:
                        response_owner_page = await self.http_client.get(
                            f"{self.backend_url}/utils/{owner_id}/lists/{list_id}/current_page/", timeout=10)
                        response_owner_page.raise_for_status()
                        owner_current_page = response_owner_page.json().get("current_page", 1)
                    except httpx.HTTPError as e:
                        logger.error(f"Ошибка получения текущей страницы владельца {owner_id}: {e}")
                        owner_current_page = 1
                    await self.update_shopping_list_message(chat_id=list_data['owner_id'], user_id=owner_id,
                                                            list_id=list_id, current_page=owner_current_page,
                                                            notification_text=notification_text_to_store)
                    if user_id != owner_id:
                        try:
                            response_page = await self.http_client.get(
                                f"{self.backend_url}/utils/{user_id}/lists/{list_id}/current_page/", timeout=10)
                            response_page.raise_for_status()
                            current_page = response_page.json().get("current_page", 1)
                        except httpx.HTTPError as e:
                            logger.error(f"Ошибка получения текущей страницы пользователя {user_id}: {e}")
                            current_page = 1
                        await self.update_shopping_list_message(chat_id, user_id, list_id, current_page,
                                                                notification_text=notification_text_to_store)

                elif action_type != "unsubscribe":
                    if exclude_user_id != user_id:
                        try:
                            response_page = await self.http_client.get(
                                f"{self.backend_url}/utils/{user_id}/lists/{list_id}/current_page/", timeout=10)
                            response_page.raise_for_status()
                            current_page = response_page.json().get("current_page", 1)
                        except httpx.HTTPError as e:
                            logger.error(f"Ошибка получения текущей страницы пользователя {user_id}: {e}")
                            current_page = 1

                        notification_to_pass = notification_text_to_store if notification_text_to_store else None
                        await self.update_shopping_list_message(chat_id, user_id, list_id, current_page,
                                                                notification_to_pass)

            except httpx.HTTPError as e:
                logger.warning(f"Ошибка при обработке уведомления для пользователя {user_id}: {e}")
                continue

        if notification_text_to_store:
            try:
                await self.http_client.post(f"{self.backend_url}/lists/{list_id}/notification/",
                                            json={"notification_text": notification_text_to_store}, timeout=10)
            except httpx.HTTPError as e:
                logger.error(f"Ошибка сохранения уведомления на бэкенде: {e}")
