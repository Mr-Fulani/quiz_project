from aiogram.fsm.state import StatesGroup, State

class PasswordStates(StatesGroup):
    waiting_for_password = State()

class RegistrationStates(StatesGroup):
    waiting_for_details = State()

class AddAdminStates(StatesGroup):
    waiting_for_confirmation = State()
    waiting_for_groups = State()
    waiting_for_admin_data = State
    waiting_for_password = State()
    waiting_for_user_id = State()

class AdminStates(StatesGroup):
    waiting_for_set_fallback_language = State()
    waiting_for_remove_fallback_language = State()
    waiting_for_get_fallback_language = State()
    waiting_for_set_fallback_link = State()
    waiting_for_topic_name = State()
    waiting_for_topic_id = State()

class RemoveAdminStates(StatesGroup):
    waiting_for_confirmation = State()
    waiting_for_password = State()
    waiting_for_user_id = State()
    waiting_for_groups = State()  # Новое состояние для выбора групп

class ManageAdminGroupsStates(StatesGroup):
    waiting_for_admin_groups_to_remove = State()
    waiting_for_admin_id = State()
    waiting_for_group_action = State()
    waiting_for_groups_to_remove = State()
    waiting_for_groups_to_add = State()

class TaskActions(StatesGroup):
    awaiting_publish_id = State()
    awaiting_delete_id = State()

class ChannelStates(StatesGroup):
    waiting_for_channel_username = State()
    waiting_for_group_name = State()
    waiting_for_group_id = State()
    waiting_for_topic = State()
    waiting_for_language = State()
    waiting_for_location_type = State()
    waiting_for_remove_group_id = State()
    waiting_for_topic_creation = State()

class WebhookStates(StatesGroup):
    waiting_for_webhook_url = State()
    waiting_for_webhook_id = State()
    waiting_for_service_name = State()

class DefaultLinkStates(StatesGroup):
    waiting_for_language = State()
    waiting_for_topic = State()
    waiting_for_link = State()
    waiting_for_remove_language = State()
    waiting_for_remove_topic = State()

class UserStatsState(StatesGroup):
    waiting_for_telegram_id = State()

class FeedbackStates(StatesGroup):
    awaiting_reply = State()