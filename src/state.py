import logging
from typing import Dict, Any, Optional, Tuple, List
from src.models import NotionPageInfo, ProcessingResult

logger = logging.getLogger(__name__)

# State constants
STATE_IDLE = "IDLE"
STATE_AWAITING_PAGE_CONFIRMATION = "AWAITING_PAGE_CONFIRMATION"
STATE_AWAITING_PAGE_SELECTION = "AWAITING_PAGE_SELECTION"
STATE_AWAITING_NEW_PAGE_NAME = "AWAITING_NEW_PAGE_NAME"

# Structure: {chat_id: (state, data)}
_user_states: Dict[int, Tuple[str, Dict[str, Any]]] = {}


def set_user_state(
    chat_id: int, state: str, data: Optional[Dict[str, Any]] = None
) -> None:
    """Sets the state and associated data for a user."""
    _user_states[chat_id] = (state, data or {})
    logger.debug(f"State for chat {chat_id} set to {state} with data: {data}")


def get_user_state(chat_id: int) -> Tuple[str, Dict[str, Any]]:
    """Gets the current state and data for a user, defaults to IDLE."""
    return _user_states.get(chat_id, (STATE_IDLE, {}))


def clear_user_state(chat_id: int) -> None:
    """Resets the state for a user to IDLE."""
    if chat_id in _user_states:
        del _user_states[chat_id]
        logger.debug(f"State for chat {chat_id} cleared.")


# --- Helper functions to manage specific data within state ---


def store_pending_summary_data(
    chat_id: int,
    processing_result: ProcessingResult,
    suggested_page: NotionPageInfo,
    page_options: List[NotionPageInfo],
) -> None:
    """Stores data needed during the page confirmation/selection process."""
    data = {
        "processing_result": processing_result.model_dump(),  # Store as dict for serialization if needed later
        "suggested_page": suggested_page.model_dump(),
        "page_options": [p.model_dump() for p in page_options],
    }
    set_user_state(chat_id, STATE_AWAITING_PAGE_CONFIRMATION, data)


def get_pending_summary_data(chat_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves stored data if the user is in a relevant state."""
    state, data = get_user_state(chat_id)
    if state in [
        STATE_AWAITING_PAGE_CONFIRMATION,
        STATE_AWAITING_PAGE_SELECTION,
        STATE_AWAITING_NEW_PAGE_NAME,
    ]:
        # Reconstruct Pydantic models if needed, though often dicts are fine here
        # For simplicity, we'll work with dicts retrieved from state
        return data
    return None
