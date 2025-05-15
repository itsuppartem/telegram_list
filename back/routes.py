import logging
from typing import Union

from fastapi import APIRouter, Depends, HTTPException

from database import Database
from models import *

logger = logging.getLogger(__name__)

router = APIRouter()


def get_database():
    database = Database()
    try:
        yield database
    finally:
        database.client.close()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/users/{user_id}/", response_model=Union[UserResponse, dict])
async def get_user_endpoint(user_id: int, db: Database = Depends(get_database)):
    logger.debug(f"get_user_endpoint: user_id={user_id}")
    user_data = await db.get_user(user_id)
    if user_data:
        return user_data
    else:
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/users/{user_id}/last_subscribed_list/", response_model=LastSubscribedListResponse)
async def get_user_last_subscribed_list(user_id: int, db: Database = Depends(get_database)):
    logger.debug(f"get_user_last_subscribed_list: user_id={user_id}")
    last_subscribed_list_id = await db.get_last_subscribed_list_id(user_id)
    return {"last_subscribed_list_id": last_subscribed_list_id}


@router.post("/utils/{user_id}/lists/{list_id}/last_message/")
async def set_last_list_message_endpoint(user_id: int, list_id: str, request: SetLastMessageRequest,
                                         db: Database = Depends(get_database)):
    logger.debug(
        f"set_last_list_message_endpoint: user_id={user_id}, list_id={list_id}, message_id={request.message_id}")
    await db.set_last_list_message(user_id, list_id, request.message_id)
    return {"status": "last_message set"}


@router.get("/lists/{list_id}/", response_model=ListResponse)
async def get_list(list_id: str, db: Database = Depends(get_database)):
    logger.debug(f"get_list_endpoint: list_id={list_id}")
    list_data = await db._get_list(list_id)
    if list_data:
        return list_data
    else:
        raise HTTPException(status_code=404, detail="List not found")


@router.post("/users/actions/")
async def update_action(request: UserActionRequest, db: Database = Depends(get_database)):
    logger.debug(
        f"update_action_endpoint: user_id={request.user_id}, chat_id={request.chat_id}, username={request.username}")
    await db.update_user_action(request.user_id, request.chat_id, request.username)
    return {"status": "action updated"}


@router.post("/lists/", response_model=CreateListResponse)
async def create_list(user_id: int, db: Database = Depends(get_database)):
    logger.debug(f"create_list_endpoint: user_id={user_id}")
    list_id = await db.create_new_list(user_id)
    return {"list_id": list_id}


@router.get("/users/{user_id}/lists/", response_model=UserListsResponse)
async def get_lists_for_user(user_id: int, db: Database = Depends(get_database)):
    logger.debug(f"get_lists_for_user_endpoint: user_id={user_id}")
    lists = await db.get_user_lists(user_id)
    return {"lists": lists}


@router.get("/lists/{list_id}/items/", response_model=ListItemsResponse)
async def get_items_for_list(list_id: str, db: Database = Depends(get_database)):
    logger.debug(f"get_items_for_list_endpoint: list_id={list_id}")
    items = await db.get_list_items(list_id)
    return {"items": items}


@router.post("/lists/{list_id}/items/")
async def add_item_to_list(list_id: str, request: AddItemRequest, db: Database = Depends(get_database)):
    logger.debug(f"add_item_to_list_endpoint: list_id={list_id}, item_name={request.item_name}")
    item_id = await db.add_shopping_item(list_id, request.item_name)
    return {"item_id": item_id, "status": "item added"}


@router.put("/lists/{list_id}/items/{item_id}/toggle/")
async def toggle_item_in_list(list_id: str, item_id: str, db: Database = Depends(get_database)):
    logger.debug(f"toggle_item_in_list_endpoint: list_id={list_id}, item_id={item_id}")
    await db.toggle_shopping_item(list_id, item_id)
    return {"status": "item toggled"}


@router.delete("/lists/{list_id}/items/{item_id}/")
async def delete_item_from_list(list_id: str, item_id: str, db: Database = Depends(get_database)):
    logger.debug(f"delete_item_from_list_endpoint: list_id={list_id}, item_id={item_id}")
    await db.delete_shopping_item(list_id, item_id)
    return {"status": "item deleted"}


@router.post("/lists/{list_id}/complete/")
async def complete_shopping_list(list_id: str, db: Database = Depends(get_database)):
    logger.debug(f"complete_shopping_list_endpoint: list_id={list_id}")
    users, items, last_message_ids_for_users = await db.complete_list(list_id)
    return {"status": "list completed", "users": users, "items": items,
            "last_message_ids_for_users": last_message_ids_for_users}


@router.get("/utils/{user_id}/lists/{list_id}/skip_confirm/")
async def get_list_skip_confirm(user_id: int, list_id: str, db: Database = Depends(get_database)):
    logger.debug(f"get_list_skip_confirm_endpoint: user_id={user_id}, list_id={list_id}")
    skip_confirm = await db.get_skip_confirm(user_id, list_id)
    return {"skip_confirm": skip_confirm}


@router.post("/utils/{user_id}/lists/{list_id}/skip_confirm/")
async def set_list_skip_confirm(user_id: int, list_id: str, request: SetSkipConfirmRequest,
                                db: Database = Depends(get_database)):
    logger.debug(f"set_list_skip_confirm_endpoint: user_id={user_id}, list_id={list_id}, value={request.value}")
    await db.set_skip_confirm(user_id, list_id, request.value)
    return {"status": "skip_confirm updated"}


@router.delete("/utils/{user_id}/lists/{list_id}/skip_confirm/")
async def delete_list_skip_confirm(user_id: int, list_id: str, db: Database = Depends(get_database)):
    logger.debug(f"delete_list_skip_confirm_endpoint: user_id={user_id}, list_id={list_id}")
    await db.delete_skip_confirm(user_id, list_id)
    return {"status": "skip_confirm deleted"}


@router.post("/lists/{list_id}/share/")
async def share_shopping_list(list_id: str, request: ShareListRequest, db: Database = Depends(get_database)):
    logger.debug(f"share_shopping_list_endpoint: list_id={list_id}, user_id={request.user_id}")
    success = await db.share_list(list_id, request.user_id)
    if success:
        return {"status": "list shared", "user_added": request.user_id}
    else:
        raise HTTPException(status_code=400,
                            detail="Could not share list. User might already be in this or another list, or list does not exist.")


@router.post("/lists/{list_id}/unsubscribe/")
async def unsubscribe_shopping_list(list_id: str, request: UnsubscribeListRequest,
                                    db: Database = Depends(get_database)):
    logger.debug(f"unsubscribe_shopping_list_endpoint: list_id={list_id}, user_id={request.user_id}")
    success = await db.unsubscribe_user_from_list(list_id, request.user_id)
    if success:
        return {"status": "unsubscribed from list", "user_removed": request.user_id}
    else:
        raise HTTPException(status_code=400,
                            detail="Could not unsubscribe from list. User might be the owner or not in the list.")


@router.get("/utils/{user_id}/lists/{list_id}/current_page/")
async def get_list_current_page(user_id: int, list_id: str, db: Database = Depends(get_database)):
    logger.debug(f"get_list_current_page_endpoint: user_id={user_id}, list_id={list_id}")
    page = await db.get_current_page(user_id, list_id)
    return {"current_page": page}


@router.post("/utils/{user_id}/lists/{list_id}/current_page/")
async def set_list_current_page(user_id: int, list_id: str, request: SetPageRequest,
                                db: Database = Depends(get_database)):
    logger.debug(f"set_list_current_page_endpoint: user_id={user_id}, list_id={list_id}, page={request.page}")
    await db.set_current_page(user_id, list_id, request.page)
    return {"status": "current_page updated"}


@router.delete("/utils/{user_id}/lists/{list_id}/current_page/")
async def delete_list_current_page(user_id: int, list_id: str, db: Database = Depends(get_database)):
    logger.debug(f"delete_list_current_page_endpoint: user_id={user_id}, list_id={list_id}")
    await db.delete_current_page(user_id, list_id)
    return {"status": "current_page deleted"}


@router.delete("/utils/{user_id}/lists/{list_id}/last_message/{message_id}/")
async def delete_last_list_message_endpoint(user_id: int, list_id: str, message_id: int,
                                            db: Database = Depends(get_database)):
    logger.debug(f"delete_last_list_message_endpoint: user_id={user_id}, list_id={list_id}, message_id={message_id}")
    await db.delete_last_list_message(user_id, list_id, message_id)
    return {"status": "last_message deleted"}


@router.get("/utils/{user_id}/lists/{list_id}/last_message/")
async def get_last_list_message_endpoint(user_id: int, list_id: str, db: Database = Depends(get_database)):
    logger.debug(f"get_last_list_message_endpoint: user_id={user_id}, list_id={list_id}")
    message_ids = await db.get_last_list_message(user_id, list_id)
    logger.debug(f"get_last_list_message_endpoint: Returning last_message_ids: {message_ids}")
    return {"last_message_ids": message_ids}


@router.delete("/utils/{user_id}/lists/{list_id}/last_message/clear/")
async def clear_all_last_list_message_endpoint(user_id: int, list_id: str, db: Database = Depends(get_database)):
    logger.debug(f"clear_all_last_list_message_endpoint: user_id={user_id}, list_id={list_id}")
    await db.clear_all_last_list_messages(user_id, list_id)
    return {"status": "all last messages cleared"}


@router.delete("/utils/{user_id}/lists/{list_id}/last_message/{message_id}/delete_one/")
async def delete_one_last_list_message_endpoint(user_id: int, list_id: str, message_id: int,
                                                db: Database = Depends(get_database)):
    logger.debug(
        f"delete_one_last_list_message_endpoint: user_id={user_id}, list_id={list_id}, message_id={message_id}")
    await db.delete_one_last_list_message(user_id, list_id, message_id)
    return {"status": "last_message deleted", "message_id": message_id}


@router.post("/lists/{list_id}/notification/")
async def set_list_notification_endpoint(list_id: str, request: NotificationRequest,
                                         db: Database = Depends(get_database)):
    logger.debug(f"set_list_notification_endpoint: list_id={list_id}")
    await db.set_list_notification_text(list_id, request.notification_text)
    return {"status": "notification text set"}


@router.post("/lists/{list_id}/clear_notification/")
async def clear_list_notification_endpoint(list_id: str, db: Database = Depends(get_database)):
    logger.debug(f"clear_list_notification_endpoint: list_id={list_id}")
    await db.clear_list_notification_text(list_id)
    return {"status": "notification text cleared"}


@router.post("/users/{user_id}/clear_last_subscribed_list/")
async def clear_user_last_subscribed_list(user_id: int, db: Database = Depends(get_database)):
    logger.debug(f"clear_user_last_subscribed_list_endpoint: user_id={user_id}")
    await db.clear_last_subscribed_list_id(user_id)
    return {"status": "last_subscribed_list_id cleared"}


@router.post("/lists/{list_id}/items/bulk/", response_model=AddBulkItemsResponse)
async def add_bulk_items_to_list(list_id: str, request: AddItemsRequest, db: Database = Depends(get_database)):
    logger.debug(f"add_bulk_items_to_list_endpoint: list_id={list_id}, items={request.items}")
    item_names = [item.item_name for item in request.items]
    added_item_names = await db.add_shopping_items_bulk(list_id, item_names)
    return {"added_items": added_item_names}
