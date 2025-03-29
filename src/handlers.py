import logging
from telegram import Update, MessageEntity
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)
from functools import wraps

from src.config import APP_CONFIG
from src.logic import (
    process_audio_message,
    process_text_message,
    reset_state_command,
    handle_page_confirmation_callback,
    handle_page_rejection_callback,
    handle_page_selection_callback,
    handle_new_page_callback,
)
from src.services import telegram_service
from src.state import clear_user_state

logger = logging.getLogger(__name__)


# --- Decorator for Authorization ---
def authorized_user_only(func):
    """Decorator to restrict access to allowed Telegram user IDs."""

    @wraps(func)
    async def wrapped(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        user = update.effective_user
        if not user:
            logger.warning("Cannot identify user in update.")
            return

        if (
            APP_CONFIG.allowed_telegram_user_ids
            and user.id not in APP_CONFIG.allowed_telegram_user_ids
        ):
            logger.warning(
                f"Unauthorized access attempt by user ID: {user.id} ({user.username})"
            )
            return
        # User is authorized, proceed with the original function
        return await func(update, context, *args, **kwargs)

    return wrapped


# --- Command Handlers ---
@authorized_user_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started interaction.")
    clear_user_state(update.effective_chat.id)  # Clear state on start
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm AuditLife bot. Send me text or voice notes to process and document.",
    )


@authorized_user_only
async def reset_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handler for the /reset command."""
    await reset_state_command(update, context)


# --- Message Handlers ---
@authorized_user_only
async def text_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handler for incoming text messages (excluding commands)."""
    # Ignore commands handled elsewhere
    if (
        update.message
        and update.message.entities
        and any(e.type == MessageEntity.BOT_COMMAND for e in update.message.entities)
    ):
        return
    await process_text_message(update, context)


@authorized_user_only
async def audio_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handler for incoming audio/voice messages."""
    await process_audio_message(update, context)


# --- Callback Query Handler ---
@authorized_user_only
async def button_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles callbacks from inline keyboard buttons."""
    query = update.callback_query
    if not query or not query.data:
        logger.warning("Received callback query without data.")
        await query.answer("Error: No callback data received.")
        return

    logger.debug(f"Received callback query with data: {query.data}")

    # Route based on callback data prefix
    if query.data.startswith(telegram_service.CALLBACK_CONFIRM_PAGE):
        await handle_page_confirmation_callback(update, context)
    elif query.data == telegram_service.CALLBACK_REJECT_PAGE:
        await handle_page_rejection_callback(update, context)
    elif query.data.startswith(telegram_service.CALLBACK_SELECT_PAGE):
        await handle_page_selection_callback(update, context)
    elif query.data == telegram_service.CALLBACK_NEW_PAGE:
        await handle_new_page_callback(update, context)
    else:
        logger.warning(f"Unhandled callback query data: {query.data}")
        await query.answer("Unknown action.")  # Let the user know it wasn't processed


# --- Error Handler ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs errors caused by Updates."""
    logger.error(
        f"Update {update} caused error {context.error}", exc_info=context.error
    )
    # Optionally notify user or admin
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, an internal error occurred. Please try again later.",
            )
        except Exception as e:
            logger.error(
                f"Failed to send error message to chat {update.effective_chat.id}: {e}"
            )


# --- Define Handlers List ---
# Order matters sometimes, especially for MessageHandlers
HANDLERS = [
    CommandHandler("start", start_command),
    CommandHandler("reset", reset_command_handler),
    MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler),
    MessageHandler(filters.AUDIO | filters.VOICE, audio_message_handler),
    CallbackQueryHandler(button_callback_handler),
]
