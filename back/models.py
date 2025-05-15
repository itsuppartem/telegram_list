from typing import List, Dict, Optional

from pydantic import BaseModel


class UserActionRequest(BaseModel):
    user_id: int
    chat_id: int
    username: str


class UserResponse(BaseModel):
    _id: Optional[str] = None
    user_id: int
    chat_id: int
    username: str
    last_actions: Optional[List[str]] = None
    list_ids: Optional[List[str]] = None
    last_subscribed_list_id: Optional[str] = None


class CreateListResponse(BaseModel):
    list_id: str


class UserListsResponse(BaseModel):
    lists: List[Dict]


class ListItemsResponse(BaseModel):
    items: Dict[str, Dict]


class AddItemRequest(BaseModel):
    item_name: str


class ToggleItemRequest(BaseModel):
    item_id: str


class DeleteItemRequest(BaseModel):
    item_id: str


class ShareListRequest(BaseModel):
    user_id: int


class UnsubscribeListRequest(BaseModel):
    user_id: int


class SetPageRequest(BaseModel):
    page: int


class SetSkipConfirmRequest(BaseModel):
    value: bool


class SetLastMessageRequest(BaseModel):
    message_id: int


class ListResponse(BaseModel):
    _id: str
    owner_id: int
    users: List[int]
    items: List[Dict]
    completed: bool
    last_notification_text: Optional[str] = None


class LastSubscribedListResponse(BaseModel):
    last_subscribed_list_id: Optional[str] = None


class NotificationRequest(BaseModel):
    notification_text: str


class AddItemsRequest(BaseModel):
    items: List[AddItemRequest]


class AddBulkItemsResponse(BaseModel):
    added_items: List[str]
