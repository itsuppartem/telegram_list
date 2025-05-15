import logging

import httpx
from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from utils import BotUtils

logger = logging.getLogger(__name__)


class Handlers:
    def __init__(self, bot_utils: BotUtils):
        self.bot_utils = bot_utils
        self.router = Router()
        self._setup_routers()

    def _setup_routers(self):
        self.router.message.register(self.start_route, Command('start'))
        self.router.message.register(self.handle_shopping_list)
        self.router.callback_query.register(self.handle_callback)

    async def start_route(self, message: Message):
        user_id = await self.bot_utils.extract_id_and_send_typing(message)
        if user_id is None:
            return

        username = message.from_user.username or "Unknown"
        user_action_data = {"user_id": user_id, "chat_id": message.chat.id, "username": username}
        try:
            await self.bot_utils.http_client.post(f"{self.bot_utils.backend_url}/users/actions/", json=user_action_data,
                                                  timeout=10)
        except httpx.HTTPError as e:
            logger.error(f"Ошибка обновления действия пользователя: {e}")

        if len(message.text.split()) > 1:
            list_id = message.text.split()[1]
            share_data = {"user_id": user_id}

            try:
                list_detail_response = await self.bot_utils.http_client.get(
                    f"{self.bot_utils.backend_url}/lists/{list_id}/", timeout=10)
                list_detail_response.raise_for_status()
                list_data = list_detail_response.json()
                if user_id in list_data.get("users", []):
                    await message.answer("Вы <b>уже добавлены</b> в этот список!")
                    return

                response = await self.bot_utils.http_client.post(f"{self.bot_utils.backend_url}/lists/{list_id}/share/",
                                                                 json=share_data, timeout=10)
                if response.status_code == 400:
                    error_detail = response.json().get("detail", "")
                    if "User might already be in this or another list" in error_detail:
                        await message.answer("Вы <b>уже состоите в другом списке!</b>")
                    else:
                        await message.answer("<b>Не удалось добавить</b> в список. Ошибка 400.")
                else:
                    response.raise_for_status()
                    await message.answer("Вы <b>добавлены</b> в список!")
                    await self.bot_utils.update_shopping_list_message(message.chat.id, user_id, list_id)

            except httpx.HTTPError as e:
                logger.error(f"Ошибка добавления в список: {e}")
                await message.answer("<b>Не удалось добавить</b> в список.")
        else:
            try:
                response = await self.bot_utils.http_client.get(f"{self.bot_utils.backend_url}/users/{user_id}/lists/",
                                                                timeout=10)
                response.raise_for_status()
                user_lists_data = response.json()
                user_lists = user_lists_data.get("lists", [])

                filtered_lists = []

                for lst in user_lists:
                    if lst.get('owner_id') != user_id in lst.get('users', []):
                        filtered_lists.append(lst)

                logger.info(filtered_lists)

                try:
                    list_id = filtered_lists[0].get("_id") or await self._get_or_create_list(user_id)
                except:
                    list_id = await self._get_or_create_list(user_id)
                logger.info(list_id)
                try:
                    list_detail_response = await self.bot_utils.http_client.get(
                        f"{self.bot_utils.backend_url}/lists/{list_id}/", timeout=10)
                    list_detail_response.raise_for_status()
                    list_data = list_detail_response.json()
                    items = list_data.get("items", [])

                    if not items:
                        welcome_text = ("Привет!\n\nЯ бот для <b>создания списков.</b>\n\n"
                                        "Чтобы составить список, <b>отправьте мне информацию:</b>\n"
                                        "- <u>Отдельными</u> сообщениями\n"
                                        "- <u>Одним сообщением</u>, каждый пункт с новой строки\n"
                                        "- <u>Пересылайте</u> сообщения из других чатов\n\n"
                                        "<i>Активным будет <b>только 1 список</b> (приоритет отдается списку, которым с вами поделились)</i>")
                        await message.answer(welcome_text, parse_mode=ParseMode.HTML)
                    pass
                except httpx.HTTPError as e:
                    logger.error(f"Ошибка получения деталей списка для проверки пустоты: {e}")
                    pass

            except httpx.HTTPError as e:
                logger.error(f"Ошибка получения или создания списка: {e}")
                await message.answer("<b>Ошибка</b> при работе со списками.")
                return

            try:
                response = await self.bot_utils.http_client.get(
                    f"{self.bot_utils.backend_url}/utils/{user_id}/lists/{list_id}/last_message/", timeout=10)
                response.raise_for_status()
                last_message_ids = response.json().get("last_message_ids", [])
                for msg_id in last_message_ids:
                    await self.bot_utils.bot.delete_message(message.chat.id, msg_id)
                    await self.bot_utils.http_client.delete(
                        f"{self.bot_utils.backend_url}/utils/{user_id}/lists/{list_id}/last_message/{msg_id}/",
                        timeout=10)
            except Exception as e:
                logger.error(f"<b>Ошибка удаления</b> старых сообщений: {e}")

        if not len(message.text.split()) > 1:
            await self.bot_utils.update_shopping_list_message(message.chat.id, user_id, list_id)

    async def _get_or_create_list(self, user_id):
        response = await self.bot_utils.http_client.get(f"{self.bot_utils.backend_url}/users/{user_id}/lists/",
                                                        timeout=10)
        response.raise_for_status()
        user_lists = response.json().get("lists", [])
        if not user_lists:
            create_response = await self.bot_utils.http_client.post(
                f"{self.bot_utils.backend_url}/lists/?user_id={user_id}", timeout=10)
            create_response.raise_for_status()
            return create_response.json().get("list_id")
        active_list = next((lst for lst in user_lists if not lst.get("completed", False)), user_lists[0])
        return active_list["_id"]

    async def handle_shopping_list(self, message: Message):
        user_id = await self.bot_utils.extract_id_and_send_typing(message)
        if user_id is None:
            return

        username = message.from_user.username or "Unknown"
        user_action_data = {"user_id": user_id, "chat_id": message.chat.id, "username": username}
        try:
            await self.bot_utils.http_client.post(f"{self.bot_utils.backend_url}/users/actions/", json=user_action_data,
                                                  timeout=10)
        except httpx.HTTPError as e:
            logger.error(f"Ошибка обновления действия пользователя: {e}")

        if message.content_type != "text":
            await message.reply("Поддерживаются <b>только текстовые сообщения.</b>")
            await self.bot_utils.bot.delete_message(message.chat.id, message.message_id)
            return

        try:
            response = await self.bot_utils.http_client.get(
                f"{self.bot_utils.backend_url}/users/{user_id}/last_subscribed_list/", timeout=10)
            response.raise_for_status()
            list_id = response.json().get("last_subscribed_list_id") or await self._get_or_create_list(user_id)
        except httpx.HTTPError as e:
            logger.error(f"Ошибка получения списка: {e}")
            await message.reply("<b>Ошибка</b> при работе со списками.")
            return

        text = message.text or message.caption or ""
        items = [item.strip() for item in text.split('\n') if item.strip()]

        if not items:
            return

        try:
            response = await self.bot_utils.http_client.post(
                f"{self.bot_utils.backend_url}/lists/{list_id}/items/bulk/",
                json={"items": [{"item_name": item} for item in items]}, timeout=10)
            response.raise_for_status()
            added_items = response.json().get("added_items", [])
            if not added_items:
                added_items = items

            if added_items:
                last_item = added_items[-1]
                await self.bot_utils.notify_list_change(list_id, user_id, action_type="add", item_name=last_item)
        except httpx.HTTPError as e:
            logger.error(f"Ошибка добавления элементов списка: {e}")
            await message.reply(f"<b>Не удалось</b> добавить элементы списка.")

        await self.bot_utils.update_shopping_list_message(message.chat.id, user_id, list_id)
        try:
            await self.bot_utils.bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение: {e}")

    async def handle_callback(self, callback: CallbackQuery):
        user_id = callback.from_user.id
        username = callback.from_user.username or "Unknown"
        user_action_data = {"user_id": user_id, "chat_id": callback.message.chat.id, "username": username}
        try:
            await self.bot_utils.http_client.post(f"{self.bot_utils.backend_url}/users/actions/", json=user_action_data,
                                                  timeout=10)
        except httpx.HTTPError as e:
            logger.error(f"Ошибка обновления действия пользователя: {e}")

        parts = callback.data.split("_")
        action = parts[0]

        if action == "sort" and parts[1] == "list":
            list_id = parts[2]
            current_page = int(parts[3])
            current_sort_state = self.bot_utils.sort_states.get(list_id, False)
            self.bot_utils.sort_states[list_id] = not current_sort_state
            await self.bot_utils.update_shopping_list_message(callback.message.chat.id, user_id, list_id, current_page)
            await callback.answer(
                "Список отсортирован по алфавиту" if not current_sort_state else "Сортировка отменена")
            return

        if action in ["complete", "confirm"] and "complete" in callback.data:
            list_id = parts[1] if action == "complete" else parts[2]
            try:
                response = await self.bot_utils.http_client.get(f"{self.bot_utils.backend_url}/lists/{list_id}/",
                                                                timeout=10)
                response.raise_for_status()
                if response.json()["owner_id"] == user_id:
                    await self.bot_utils.complete_list(user_id, list_id)
                    await callback.answer("Список завершен!")
                else:
                    await callback.answer("Вы не владелец списка.")
            except httpx.HTTPError as e:
                logger.error(f"Ошибка завершения списка: {e}")
                await callback.answer("Ошибка при завершении.")
            return

        if action == "cancel" and parts[1] == "complete":
            list_id = parts[2]
            try:
                await self.bot_utils.http_client.post(
                    f"{self.bot_utils.backend_url}/utils/{user_id}/lists/{list_id}/skip_confirm/", json={"value": True},
                    timeout=10)
                await self.bot_utils.update_shopping_list_message(callback.message.chat.id, user_id, list_id)
                await callback.answer("Список остается активным.")
            except httpx.HTTPError as e:
                logger.error(f"Ошибка отмены завершения: {e}")
                await callback.answer("Ошибка при отмене.")
            return

        if action in ["prev", "next"] and len(parts) == 3:
            list_id, current_page = parts[1], int(parts[2])
            if action == "prev":
                await callback.answer(f"Вы на странице {int(parts[2]) - 1}")
            else:
                await callback.answer(f"Вы на странице {int(parts[2]) + 1}")
            new_page = current_page - 1 if action == "prev" else current_page + 1
            try:
                await self.bot_utils.http_client.post(
                    f"{self.bot_utils.backend_url}/utils/{user_id}/lists/{list_id}/current_page/",
                    json={"page": new_page}, timeout=10)
            except httpx.HTTPError as e:
                logger.error(f"Ошибка сохранения страницы: {e}")
            await self.bot_utils.update_shopping_list_message(callback.message.chat.id, user_id, list_id, new_page)
            return

        if action == "page":
            await callback.answer(f"Вы на странице {parts[2]}")
            return

        if action in ["disabled_prev", "disabled_next"]:
            await callback.answer("Вы на первой странице" if action == "disabled_prev" else "Вы на последней странице")
            return

        if action == "share":
            list_id = parts[1]
            bot_username = (await self.bot_utils.bot.get_me()).username
            await callback.message.answer(f"Поделитесь ссылкой: t.me/{bot_username}?start={list_id}")
            return

        if action == "unsubscribe":
            list_id = parts[1]
            try:
                await self.bot_utils.http_client.post(f"{self.bot_utils.backend_url}/lists/{list_id}/unsubscribe/",
                                                      json={"user_id": user_id}, timeout=10)
                await callback.answer("Вы отписались от списка.", show_alert=True)
                await callback.message.delete()
                await self.bot_utils.notify_list_change(list_id, user_id, action_type="unsubscribe")
            except httpx.HTTPError as e:
                logger.error(f"Ошибка отписки: {e}")
                await callback.answer("Не удалось отписаться.", show_alert=True)
            return

        if len(parts) < 4:
            return

        list_id, item_id, page = parts[1], parts[2], int(parts[3])
        try:
            response = await self.bot_utils.http_client.get(f"{self.bot_utils.backend_url}/lists/{list_id}/items/",
                                                            timeout=10)
            response.raise_for_status()
            items = response.json().get("items", {})
        except httpx.HTTPError as e:
            logger.error(f"Ошибка получения элементов списка: {e}")
            items = {}

        if action == "toggle" and item_id in items:
            try:
                await self.bot_utils.http_client.put(
                    f"{self.bot_utils.backend_url}/lists/{list_id}/items/{item_id}/toggle/", timeout=10)
                await self.bot_utils.http_client.delete(
                    f"{self.bot_utils.backend_url}/utils/{user_id}/lists/{list_id}/skip_confirm/", timeout=10)
                response = await self.bot_utils.http_client.get(f"{self.bot_utils.backend_url}/lists/{list_id}/items/",
                                                                timeout=10)
                updated_items = response.json().get("items", {})
                status = "выполнено" if updated_items[item_id]["bought"] else "не выполнено"
                alert_text = f"Статус '{updated_items[item_id]['name']}' изменен на {status}"
                item_name = updated_items[item_id]["name"]
                await self.bot_utils.notify_list_change(list_id, user_id, action_type="toggle", item_name=item_name)
            except httpx.HTTPError as e:
                logger.error(f"Ошибка изменения статуса: {e}")
                alert_text = "Не удалось изменить статус."
        elif action == "delete" and item_id in items:
            try:
                item_name = items[item_id]["name"]
                await self.bot_utils.http_client.delete(
                    f"{self.bot_utils.backend_url}/lists/{list_id}/items/{item_id}/", timeout=10)
                await self.bot_utils.http_client.delete(
                    f"{self.bot_utils.backend_url}/utils/{user_id}/lists/{list_id}/skip_confirm/", timeout=10)
                alert_text = f"'{item_name}' удален из списка"
                await self.bot_utils.notify_list_change(list_id, user_id, action_type="delete", item_name=item_name)
            except httpx.HTTPError as e:
                logger.error(f"Ошибка удаления элемента: {e}")
                alert_text = "Не удалось удалить элемент."
        elif action == "none" and item_id in items:
            await callback.answer(f"'{items[item_id]['name']}' - выберите действие")
            return
        else:
            return

        await self.bot_utils.update_shopping_list_message(callback.message.chat.id, user_id, list_id, page)
        await callback.answer(alert_text or "")
