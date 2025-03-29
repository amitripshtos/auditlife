import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.models import NotionPageInfo

logger = logging.getLogger(__name__)

# --- Constants for Callback Data ---
CALLBACK_CONFIRM_PAGE = "confirm_page_"
CALLBACK_REJECT_PAGE = "reject_page"
CALLBACK_SELECT_PAGE = "select_page_"
CALLBACK_NEW_PAGE = "new_page"


async def reply_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    """Safely replies to a message."""
    if update.effective_message:
        await update.effective_message.reply_text(text)
    else:
        logger.warning("Cannot reply, update.effective_message is None.")


async def send_page_confirmation_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    suggested_page: NotionPageInfo,
    summary: str,
) -> None:
    """Asks the user to confirm the suggested Notion page for the summary."""
    keyboard = [
        [
            InlineKeyboardButton(
                f"✅ Yes, add to '{suggested_page.title}'",
                callback_data=f"{CALLBACK_CONFIRM_PAGE}{suggested_page.id}",
            ),
        ],
        [
            InlineKeyboardButton(
                "❌ No, choose another page", callback_data=CALLBACK_REJECT_PAGE
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Here's the summary:\n\n---\n{summary}\n---\n\nShould I add this to the Notion page '{suggested_page.title}'?"
    if update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=reply_markup)
    else:
        logger.warning(
            "Cannot send confirmation prompt, update.effective_message is None."
        )


async def send_page_selection_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page_options: list[NotionPageInfo],
) -> None:
    """Shows available Notion pages and asks the user to choose or create new."""
    if not page_options:
        keyboard = [
            [
                InlineKeyboardButton(
                    "✨ Create New Page", callback_data=CALLBACK_NEW_PAGE
                )
            ]
        ]
        text = "I couldn't find any relevant pages under the configured parent. Would you like to create a new page for the summary?"
    else:
        keyboard = [
            [
                InlineKeyboardButton(
                    f"📄 {page.title}", callback_data=f"{CALLBACK_SELECT_PAGE}{page.id}"
                )
            ]
            for page in page_options
        ]
        # Add the 'Create New Page' option at the end
        keyboard.append(
            [
                InlineKeyboardButton(
                    "✨ Create New Page", callback_data=CALLBACK_NEW_PAGE
                )
            ]
        )
        text = "Please choose a Notion page to add the summary to, or create a new one:"

    reply_markup = InlineKeyboardMarkup(keyboard)
    # Edit the previous message or send a new one
    if update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_text(
                text=text, reply_markup=reply_markup
            )
        except (
            Exception
        ) as e:  # Handle cases where message can't be edited (e.g., too old)
            logger.warning(
                f"Failed to edit message for page selection, sending new message. Error: {e}"
            )
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    reply_markup=reply_markup,
                )
    elif update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=reply_markup)
    else:
        logger.warning("Cannot send page selection prompt, no effective message/chat.")


async def request_new_page_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Asks the user to provide a name for the new Notion page."""
    text = "Please enter the name for the new Notion page."
    # Edit the previous message or send a new one
    if update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_text(text=text)  # Remove buttons
        except Exception as e:
            logger.warning(
                f"Failed to edit message for new page name request, sending new message. Error: {e}"
            )
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, text=text
                )
    elif update.effective_message:
        await update.effective_message.reply_text(text)
    else:
        logger.warning("Cannot request new page name, no effective message/chat.")
