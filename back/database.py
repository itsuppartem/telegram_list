import logging
from datetime import datetime
from typing import List, Optional

from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGODB_URL

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGODB_URL)
        self.db = self.client.shopping_bot
        self.users = self.db.users
        self.lists = self.db.lists
        self.utils = self.db.utils
        logger.debug("Database initialized")

    async def get_user(self, user_id):
        logger.debug(f"get_user: user_id={user_id}")
        user = await self.users.find_one({"user_id": user_id})
        if user:
            user["_id"] = str(user.get("_id"))
            logger.debug(f"get_user: User found: {user}")
        else:
            logger.debug(f"get_user: User not found for user_id={user_id}")
        return user

    async def get_last_subscribed_list_id(self, user_id: int) -> Optional[str]:
        logger.debug(f"get_last_subscribed_list_id: user_id={user_id}")
        user = await self.users.find_one({"user_id": user_id})
        if user and "last_subscribed_list_id" in user:
            list_id = user["last_subscribed_list_id"]
            logger.debug(f"get_last_subscribed_list_id: User {user_id}, last_subscribed_list_id found: {list_id}")
            return list_id
        logger.debug(f"get_last_subscribed_list_id: User {user_id}, last_subscribed_list_id not found.")
        return None

    async def set_last_subscribed_list_id(self, user_id: int, list_id: str):
        logger.debug(f"set_last_subscribed_list_id: user_id={user_id}, list_id={list_id}")
        await self.users.update_one({"user_id": user_id}, {"$set": {"last_subscribed_list_id": list_id}}, upsert=True)
        logger.debug(f"set_last_subscribed_list_id: User {user_id}, last_subscribed_list_id set to {list_id}")

    async def clear_last_subscribed_list_id(self, user_id: int):
        logger.debug(f"clear_last_subscribed_list_id: user_id={user_id}")
        await self.users.update_one({"user_id": user_id}, {"$unset": {"last_subscribed_list_id": 1}})
        logger.debug(f"clear_last_subscribed_list_id: User {user_id}, last_subscribed_list_id cleared.")

    async def delete_last_list_message(self, user_id: int, list_id: str, message_id: int):
        logger.debug(f"delete_last_list_message: user_id={user_id}, list_id={list_id}, message_id={message_id}")
        await self.utils.update_one({"user_id": user_id}, {"$pull": {f"last_list_messages.{list_id}": message_id}})
        logger.debug(
            f"delete_last_list_message: Message ID deleted for user_id={user_id}, list_id={list_id}, message_id={message_id}")

    async def get_last_list_message(self, user_id: int, list_id: str) -> list | None:
        logger.debug(f"get_last_list_message: user_id={user_id}, list_id={list_id}")
        data = await self.utils.find_one({"user_id": user_id})
        if data and "last_list_messages" in data and list_id in data["last_list_messages"]:
            message_ids = data["last_list_messages"][list_id]
            logger.debug(
                f"get_last_list_message: User {user_id}, list {list_id}, returning last_message_ids: {message_ids}")
            return message_ids
        logger.debug(
            f"get_last_list_message: User {user_id}, list {list_id}, no last_message_ids found, returning empty list.")
        return []

    async def set_last_list_message(self, user_id: int, list_id: str, message_id: int):
        logger.debug(
            f"set_last_list_message: User {user_id}, list {list_id}, message_id: {message_id}. Attempting to save to DB.")
        await self.utils.update_one({"user_id": user_id},
            {"$push": {f"last_list_messages.{list_id}": {"$each": [message_id], "$slice": -3}}}, upsert=True)
        logger.debug(
            f"set_last_list_message: User {user_id}, list {list_id}, message_id: {message_id}. Saved to DB successfully.")

    async def get_current_page(self, user_id: int, list_id: str) -> int:
        logger.debug(f"get_current_page: user_id={user_id}, list_id={list_id}")
        data = await self.utils.find_one({"user_id": user_id})
        if data and "current_pages" in data and list_id in data["current_pages"]:
            page = data["current_pages"][list_id]
            logger.debug(f"get_current_page: User {user_id}, list {list_id}, returning page: {page}")
            return page
        logger.debug(f"get_current_page: User {user_id}, list {list_id}, no current_page found, returning default 1.")
        return 1

    async def set_current_page(self, user_id: int, list_id: str, page: int):
        logger.debug(f"set_current_page: user_id={user_id}, list_id={list_id}, page={page}")
        await self.utils.update_one({"user_id": user_id}, {"$set": {f"current_pages.{list_id}": page}}, upsert=True)
        logger.debug(f"set_current_page: Page set for user_id={user_id}, list_id={list_id}, page={page}")

    async def delete_current_page(self, user_id: int, list_id: str):
        logger.debug(f"delete_current_page: user_id={user_id}, list_id={list_id}")
        await self.utils.update_one({"user_id": user_id}, {"$unset": {f"current_pages.{list_id}": ""}})
        logger.debug(f"delete_current_page: Current page deleted for user_id={user_id}, list_id={list_id}")

    async def update_user_action(self, user_id, chat_id, username):
        timestamp = datetime.now().isoformat()
        logger.debug(f"update_user_action: user_id={user_id}, chat_id={chat_id}, username={username}")
        user = await self.users.find_one({"user_id": user_id})
        actions = user.get("last_actions", []) if user else []
        actions = [timestamp] + actions[:2]

        await self.users.update_one({"user_id": user_id},
            {"$set": {"chat_id": chat_id, "username": username, "last_actions": actions}}, upsert=True)
        logger.debug(f"update_user_action: User action updated for user_id={user_id}")

    async def create_new_list(self, user_id):
        logger.debug(f"create_new_list: user_id={user_id}")
        result = await self.lists.insert_one(
            {"owner_id": user_id, "users": [user_id], "items": [], "completed": False, "last_notification_text": None})
        list_id = str(result.inserted_id)
        await self.users.update_one({"user_id": user_id}, {"$push": {"list_ids": list_id}})
        logger.debug(f"create_new_list: New list created with list_id={list_id} for user_id={user_id}")
        return list_id

    async def get_user_lists(self, user_id):
        logger.debug(f"get_user_lists: user_id={user_id}")
        user = await self.users.find_one({"user_id": user_id})
        list_ids = user.get("list_ids", []) if user else []
        lists_data = []
        for list_id in list_ids:
            list_data = await self.lists.find_one({"_id": ObjectId(list_id)})
            if list_data:
                list_data["_id"] = str(list_data["_id"])
                lists_data.append(list_data)
        logger.debug(f"get_user_lists: Returning lists for user_id={user_id}: {lists_data}")
        return lists_data

    async def _get_list(self, list_id):
        logger.debug(f"_get_list: list_id={list_id}")
        try:
            list_data = await self.lists.find_one({"_id": ObjectId(list_id)})
            if list_data:
                list_data["_id"] = str(list_data["_id"])
                logger.debug(f"_get_list: List found: {list_data}")
                return list_data
            else:
                logger.debug(f"_get_list: List not found for list_id={list_id}")
                return None
        except Exception as e:
            logger.error(f"Invalid list_id: {list_id}. Error: {e}")
            return None

    async def get_list_items(self, list_id):
        logger.debug(f"get_list_items: list_id={list_id}")
        list_data = await self._get_list(list_id)
        if list_data:
            items = {str(item["item_id"]): {"name": item["name"], "bought": item["bought"]} for item in
                     list_data.get("items", [])}
            logger.debug(f"get_list_items: Returning items for list_id={list_id}: {items}")
            return items
        logger.debug(f"get_list_items: No list data found for list_id={list_id}, returning empty dict.")
        return {}

    async def add_shopping_item(self, list_id, item_name):
        item_id = str(ObjectId())
        logger.debug(f"add_shopping_item: list_id={list_id}, item_name={item_name}, item_id={item_id}")
        await self.lists.update_one({"_id": ObjectId(list_id)},
            {"$push": {"items": {"item_id": item_id, "name": item_name, "bought": False}}})
        logger.debug(f"add_shopping_item: Item added to list_id={list_id}, item_id={item_id}")
        return item_id

    async def toggle_shopping_item(self, list_id, item_id):
        logger.debug(f"toggle_shopping_item: list_id={list_id}, item_id={item_id}")
        list_data = await self.lists.find_one({"_id": ObjectId(list_id), "items.item_id": item_id}, {"items.$": 1})
        if not list_data or not list_data.get("items"):
            logger.warning(
                f"toggle_shopping_item: List data or items not found for list_id={list_id}, item_id={item_id}")
            return

        current_bought_status = list_data["items"][0]["bought"]
        new_bought_status = not current_bought_status

        await self.lists.update_one({"_id": ObjectId(list_id), "items.item_id": item_id},
            {"$set": {"items.$.bought": new_bought_status}})
        logger.debug(
            f"toggle_shopping_item: Item toggled in list_id={list_id}, item_id={item_id}, new_bought_status={new_bought_status}")

    async def delete_shopping_item(self, list_id, item_id):
        logger.debug(f"delete_shopping_item: list_id={list_id}, item_id={item_id}")
        await self.lists.update_one({"_id": ObjectId(list_id)}, {"$pull": {"items": {"item_id": item_id}}})
        logger.debug(f"delete_shopping_item: Item deleted from list_id={list_id}, item_id={item_id}")

    async def complete_list(self, list_id):
        logger.debug(f"complete_list: list_id={list_id}")
        list_data = await self._get_list(list_id)
        if not list_data:
            logger.warning(f"complete_list: List data not found for list_id={list_id}")
            return None, {}, {}

        await self.lists.update_one({"_id": ObjectId(list_id)}, {"$set": {"completed": True}})
        logger.debug(f"complete_list: List completed: list_id={list_id}")

        users_in_list = list_data["users"]
        last_message_ids_for_users = {}

        for user_id in users_in_list:
            data = await self.utils.find_one({"user_id": user_id})
            if data and "last_list_messages" in data and list_id in data["last_list_messages"]:
                last_message_ids_for_users[user_id] = data["last_list_messages"][list_id]
            else:
                last_message_ids_for_users[user_id] = []
            logger.debug(
                f"complete_list: User {user_id}, last_message_ids found: {last_message_ids_for_users.get(user_id)}")

        for user_id in users_in_list:
            await self.users.update_one({"user_id": user_id}, {"$pull": {"list_ids": list_id}})
            logger.debug(f"complete_list: List ID removed from user {user_id}'s list_ids.")

        for user_id in users_in_list:
            await self.utils.update_one({"user_id": user_id}, {
                "$unset": {f"last_list_messages.{list_id}": "", f"current_pages.{list_id}": "",
                    f"skip_confirm.{list_id}": "", f"last_notification_text.{list_id}": ""}})
            logger.debug(f"complete_list: List-specific data removed from utils for user {user_id}.")

        await self.lists.delete_one({"_id": ObjectId(list_id)})
        logger.debug(f"complete_list: List deleted from lists collection: list_id={list_id}")

        return users_in_list, list_data.get("items", []), last_message_ids_for_users

    async def get_skip_confirm(self, user_id: int, list_id: str) -> bool:
        logger.debug(f"get_skip_confirm: user_id={user_id}, list_id={list_id}")
        data = await self.utils.find_one({"user_id": user_id})
        if data and "skip_confirm" in data and list_id in data["skip_confirm"]:
            skip_confirm = data["skip_confirm"][list_id]
            logger.debug(f"get_skip_confirm: User {user_id}, list {list_id}, returning skip_confirm: {skip_confirm}")
            return skip_confirm
        logger.debug(f"get_skip_confirm: User {user_id}, list {list_id}, skip_confirm not found, returning False.")
        return False

    async def set_skip_confirm(self, user_id: int, list_id: str, value: bool):
        logger.debug(f"set_skip_confirm: user_id={user_id}, list_id={list_id}, value={value}")
        await self.utils.update_one({"user_id": user_id}, {"$set": {f"skip_confirm.{list_id}": value}}, upsert=True)
        logger.debug(f"set_skip_confirm: skip_confirm set for user_id={user_id}, list_id={list_id}, value={value}")

    async def delete_skip_confirm(self, user_id: int, list_id: str):
        logger.debug(f"delete_skip_confirm: user_id={user_id}, list_id={list_id}")
        await self.utils.update_one({"user_id": user_id}, {"$unset": {f"skip_confirm.{list_id}": ""}})
        logger.debug(f"delete_skip_confirm: skip_confirm deleted for user_id={user_id}, list_id={list_id}")

    async def share_list(self, list_id: str, user_id: int):
        logger.debug(f"share_list: list_id={list_id}, user_id={user_id}")
        list_data = await self._get_list(list_id)
        if not list_data:
            logger.debug(f"share_list: List not found: list_id={list_id}")
            return False

        if user_id in list_data["users"]:
            logger.debug(f"share_list: User {user_id} already in list_id={list_id}")
            return False

        user_data = await self.get_user(user_id)
        logger.info(user_data)

        try:
            id_check = user_data.get('last_subscribed_list_id')
            if id_check:
                logger.debug(f"share_list: User {user_id} already in another list.")
                return False
        except:
            pass

        await self.lists.update_one({"_id": ObjectId(list_id)}, {"$push": {"users": user_id}})
        await self.users.update_one({"user_id": user_id}, {"$push": {"list_ids": list_id}}, upsert=True)
        await self.set_last_subscribed_list_id(user_id, list_id)
        logger.debug(f"share_list: User {user_id} added to list_id={list_id}")
        return True

    async def unsubscribe_user_from_list(self, list_id: str, user_id: int):
        logger.debug(f"unsubscribe_user_from_list: list_id={list_id}, user_id={user_id}")
        list_data = await self._get_list(list_id)
        if not list_data:
            logger.warning(f"unsubscribe_user_from_list: List not found: list_id={list_id}")
            return False

        if user_id not in list_data["users"]:
            logger.warning(f"unsubscribe_user_from_list: User {user_id} is not in list_id={list_id}")
            return False

        if list_data["owner_id"] == user_id:
            logger.warning(
                f"unsubscribe_user_from_list: Owner cannot unsubscribe: user_id={user_id}, list_id={list_id}")
            return False

        await self.lists.update_one({"_id": ObjectId(list_id)}, {"$pull": {"users": user_id}})
        await self.users.update_one({"user_id": user_id}, {"$pull": {"list_ids": list_id}})
        await self.delete_current_page(user_id, list_id)
        await self.delete_last_list_message(user_id, list_id, -1)
        await self.clear_last_subscribed_list_id(user_id)
        logger.debug(f"unsubscribe_user_from_list: User {user_id} unsubscribed from list_id={list_id}")
        return True

    async def clear_all_last_list_messages(self, user_id: int, list_id: str):
        logger.debug(f"clear_all_last_list_messages: user_id={user_id}, list_id={list_id}")
        await self.utils.update_one({"user_id": user_id}, {"$unset": {f"last_list_messages.{list_id}": ""}})
        logger.debug(
            f"clear_all_last_list_messages: All last_list_messages cleared for user_id={user_id}, list_id={list_id}")

    async def delete_one_last_list_message(self, user_id: int, list_id: str, message_id: int):
        logger.debug(f"delete_one_last_list_message: user_id={user_id}, list_id={list_id}, message_id={message_id}")
        await self.utils.update_one({"user_id": user_id}, {"$pull": {f"last_list_messages.{list_id}": message_id}})
        logger.debug(
            f"delete_one_last_list_message: Message ID {message_id} deleted for user_id={user_id}, list_id={list_id}")

    async def set_list_notification_text(self, list_id: str, notification_text: str):
        logger.debug(f"set_list_notification_text: list_id={list_id}, notification_text={notification_text}")
        await self.lists.update_one({"_id": ObjectId(list_id)}, {"$set": {"last_notification_text": notification_text}})
        logger.debug(f"set_list_notification_text: Notification text set for list_id={list_id}")

    async def clear_list_notification_text(self, list_id: str):
        logger.debug(f"clear_list_notification_text: list_id={list_id}")
        await self.lists.update_one({"_id": ObjectId(list_id)}, {"$set": {"last_notification_text": None}})
        logger.debug(f"clear_list_notification_text: Notification text cleared for list_id={list_id}")

    async def add_shopping_items_bulk(self, list_id, item_names: List[str]):
        logger.debug(f"add_shopping_items_bulk: list_id={list_id}, item_names={item_names}")
        items_to_insert = []
        for item_name in item_names:
            item_id = str(ObjectId())
            items_to_insert.append({"item_id": item_id, "name": item_name, "bought": False})

        if not items_to_insert:
            return []

        await self.lists.update_one({"_id": ObjectId(list_id)}, {"$push": {"items": {"$each": items_to_insert}}})
        logger.debug(f"add_shopping_items_bulk: {len(items_to_insert)} items added to list_id={list_id}")
        return item_names
