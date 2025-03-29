import logging
import tempfile
import os
from telegram import Audio, Update, Voice
from telegram.ext import ContextTypes

from src.models import ProcessingResult, NotionPageInfo
from src.services import openai_service, notion_service, telegram_service
from src.state import (
    set_user_state,
    get_user_state,
    clear_user_state,
    store_pending_summary_data,
    get_pending_summary_data,
    STATE_AWAITING_PAGE_CONFIRMATION,
    STATE_AWAITING_PAGE_SELECTION,
    STATE_AWAITING_NEW_PAGE_NAME,
)

logger = logging.getLogger(__name__)


async def process_audio_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles incoming audio messages."""
    if not update.message or (not update.message.audio and not update.message.voice):
        logger.warning("process_audio_message called without audio message.")
        return
    if not update.effective_chat:
        logger.warning("No effective chat found for audio message.")
        return

    chat_id = update.effective_chat.id
    audio: Audio | Voice = update.message.audio or update.message.voice

    # Use a temporary file to store the downloaded audio
    try:
        # Get the file object from Telegram
        audio_file = await context.bot.get_file(audio.file_id)
        # Create a temporary file with a proper suffix (e.g., .ogg if possible, or default)
        # Telegram often sends voice notes as .ogg
        suffix = ".ogg"
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix
        ) as temp_audio_file:
            await audio_file.download_to_drive(custom_path=temp_audio_file.name)
            temp_audio_path = temp_audio_file.name
            logger.info(f"Audio downloaded to temporary file: {temp_audio_path}")

    except Exception as e:
        logger.error(f"Failed to download audio file: {e}", exc_info=True)
        await telegram_service.reply_text(
            update, context, "Sorry, I couldn't download the audio file."
        )
        return

    # Transcribe
    await telegram_service.reply_text(update, context, "🎙️ Transcribing audio...")
    transcribed_text = await openai_service.transcribe_audio(temp_audio_path)

    # Clean up the temporary file
    try:
        os.remove(temp_audio_path)
        logger.info(f"Temporary audio file removed: {temp_audio_path}")
    except OSError as e:
        logger.error(f"Error removing temporary audio file {temp_audio_path}: {e}")

    if transcribed_text:
        await telegram_service.reply_text(
            update, context, f"Transcription:\n\n{transcribed_text[:1000]}..."
        )  # Show preview
        # Now process the text
        await process_text_input(update, context, transcribed_text)
    else:
        await telegram_service.reply_text(
            update, context, "Sorry, I couldn't transcribe the audio. Please try again."
        )


async def process_text_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles incoming text messages."""
    if not update.message or not update.message.text:
        logger.warning("process_text_message called without text message.")
        return

    text = update.message.text
    # Check if the user is providing a name for a new page
    chat_id = update.effective_chat.id
    current_state, state_data = get_user_state(chat_id)

    if current_state == STATE_AWAITING_NEW_PAGE_NAME:
        await handle_new_page_name_input(update, context, text, state_data)
    else:
        # Process as regular input
        await process_text_input(update, context, text)


async def process_text_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    """Core logic to process text (either direct or transcribed)."""
    if not update.effective_chat:
        logger.warning("No effective chat found for text processing.")
        return
    chat_id = update.effective_chat.id

    # 1. Process with LLM (Translate, Facts, Summary)
    await telegram_service.reply_text(update, context, "🧠 Processing text...")
    processing_result = await openai_service.process_text_with_llm(text)

    if not processing_result:
        await telegram_service.reply_text(
            update,
            context,
            "Sorry, I encountered an error processing the text with the AI.",
        )
        clear_user_state(chat_id)
        return

    # 2. Store Facts in Notion
    if processing_result.facts:
        await telegram_service.reply_text(
            update,
            context,
            f"📝 Found {len(processing_result.facts)} facts. Adding to Notion database...",
        )
        success = await notion_service.add_facts_to_database(
            processing_result.facts, processing_result.original_text
        )
        if success:
            await telegram_service.reply_text(
                update, context, "✅ Facts successfully added to Notion."
            )
        else:
            await telegram_service.reply_text(
                update,
                context,
                "⚠️ Could not add all facts to Notion. Please check logs.",
            )
    else:
        await telegram_service.reply_text(
            update, context, "No specific facts extracted to add."
        )

    # 3. Handle Summary - Suggest Page
    summary = processing_result.summary
    if not summary:
        await telegram_service.reply_text(update, context, "No summary was generated.")
        clear_user_state(chat_id)
        return

    await telegram_service.reply_text(
        update, context, " Lising relevant Notion pages for the summary..."
    )
    page_options = await notion_service.list_pages_under_parent()

    if not page_options:
        # No pages found, ask to create new directly
        logger.info("No existing pages found. Prompting to create a new page.")
        # Store data needed if user confirms creation
        state_data = {"processing_result": processing_result.model_dump()}
        set_user_state(
            chat_id, STATE_AWAITING_NEW_PAGE_NAME, state_data
        )  # Awaiting name directly
        await telegram_service.request_new_page_name(update, context)  # Ask for name
        # Alternative: could use a button confirmation first before asking name
        # await telegram_service.send_page_selection_prompt(update, context, [])

    else:
        # Suggest the most recently edited page as a default? Or use LLM to pick?
        # Simple approach: Suggest the first one (most recently edited based on query sort)
        suggested_page = page_options[0]
        logger.info(
            f"Suggesting page '{suggested_page.title}' (ID: {suggested_page.id}) for summary."
        )

        # Store state and data for confirmation
        store_pending_summary_data(
            chat_id, processing_result, suggested_page, page_options
        )

        # Send confirmation prompt
        await telegram_service.send_page_confirmation_prompt(
            update, context, suggested_page, summary
        )


async def handle_page_confirmation_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles button press for confirming the suggested page."""
    query = update.callback_query
    await query.answer()  # Acknowledge button press

    if not query.data or not query.data.startswith(
        telegram_service.CALLBACK_CONFIRM_PAGE
    ):
        logger.warning(f"Invalid callback data for confirmation: {query.data}")
        await query.edit_message_text(text="Something went wrong. Please try again.")
        return

    if not update.effective_chat:
        logger.warning("No effective chat in confirmation callback.")
        return
    chat_id = update.effective_chat.id

    page_id_to_confirm = query.data[len(telegram_service.CALLBACK_CONFIRM_PAGE) :]
    state, stored_data = get_user_state(chat_id)
    pending_data = get_pending_summary_data(chat_id)  # Gets data if state is correct

    if state != STATE_AWAITING_PAGE_CONFIRMATION or not pending_data:
        logger.warning(
            f"Received page confirmation callback in unexpected state: {state}"
        )
        await query.edit_message_text(
            text="Your request might have timed out or is out of order. Please send the input again."
        )
        clear_user_state(chat_id)
        return

    # Reconstruct needed objects from stored dictionaries
    try:
        processing_result = ProcessingResult(**pending_data["processing_result"])
        suggested_page = NotionPageInfo(**pending_data["suggested_page"])
    except Exception as e:
        logger.error(f"Failed to reconstruct data from state: {e}", exc_info=True)
        await query.edit_message_text(
            text="Internal error loading data. Please try again."
        )
        clear_user_state(chat_id)
        return

    if suggested_page.id != page_id_to_confirm:
        logger.warning(
            f"Confirmation ID mismatch. Expected {suggested_page.id}, got {page_id_to_confirm}"
        )
        await query.edit_message_text(text="Confirmation mismatch. Please try again.")
        # Keep state for potential retry or selection? Or clear? Clearing is safer.
        clear_user_state(chat_id)
        return

    # User confirmed, append summary to the suggested page
    await query.edit_message_text(
        text=f"✅ Got it! Adding summary to Notion page '{suggested_page.title}'..."
    )
    success = await notion_service.append_text_to_page(
        suggested_page.id, f"\n{processing_result.summary}"
    )

    if success:
        await query.edit_message_text(
            text=f"✅ Summary successfully added to Notion page '{suggested_page.title}'."
        )
    else:
        await query.edit_message_text(
            text=f"⚠️ Failed to add summary to Notion page '{suggested_page.title}'."
        )

    clear_user_state(chat_id)


async def handle_page_rejection_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles button press for rejecting the suggested page, shows selection."""
    query = update.callback_query
    await query.answer()

    if not update.effective_chat:
        logger.warning("No effective chat in rejection callback.")
        return
    chat_id = update.effective_chat.id

    state, stored_data = get_user_state(chat_id)
    pending_data = get_pending_summary_data(chat_id)

    if state != STATE_AWAITING_PAGE_CONFIRMATION or not pending_data:
        logger.warning(f"Received page rejection callback in unexpected state: {state}")
        await query.edit_message_text(
            text="Your request might have timed out or is out of order. Please send the input again."
        )
        clear_user_state(chat_id)
        return

    # Reconstruct page options from stored data
    try:
        page_options_data = pending_data.get("page_options", [])
        page_options = [NotionPageInfo(**p) for p in page_options_data]
    except Exception as e:
        logger.error(
            f"Failed to reconstruct page options from state: {e}", exc_info=True
        )
        await query.edit_message_text(
            text="Internal error loading page options. Please try again."
        )
        clear_user_state(chat_id)
        return

    # Transition state and show selection prompt
    set_user_state(
        chat_id, STATE_AWAITING_PAGE_SELECTION, stored_data
    )  # Keep data, change state
    await telegram_service.send_page_selection_prompt(update, context, page_options)


async def handle_page_selection_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles button press for selecting a specific page from the list."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith(
        telegram_service.CALLBACK_SELECT_PAGE
    ):
        logger.warning(f"Invalid callback data for page selection: {query.data}")
        await query.edit_message_text(text="Something went wrong. Please try again.")
        return

    if not update.effective_chat:
        logger.warning("No effective chat in selection callback.")
        return
    chat_id = update.effective_chat.id

    selected_page_id = query.data[len(telegram_service.CALLBACK_SELECT_PAGE) :]
    state, stored_data = get_user_state(chat_id)
    pending_data = get_pending_summary_data(chat_id)  # Gets data if state is correct

    if state != STATE_AWAITING_PAGE_SELECTION or not pending_data:
        logger.warning(f"Received page selection callback in unexpected state: {state}")
        await query.edit_message_text(
            text="Your request might have timed out or is out of order. Please send the input again."
        )
        clear_user_state(chat_id)
        return

    # Reconstruct needed objects from stored dictionaries
    try:
        processing_result = ProcessingResult(**pending_data["processing_result"])
        page_options_data = pending_data.get("page_options", [])
        page_options = [NotionPageInfo(**p) for p in page_options_data]
        selected_page = next(
            (p for p in page_options if p.id == selected_page_id), None
        )
    except Exception as e:
        logger.error(
            f"Failed to reconstruct data from state for selection: {e}", exc_info=True
        )
        await query.edit_message_text(
            text="Internal error loading data. Please try again."
        )
        clear_user_state(chat_id)
        return

    if not selected_page:
        logger.error(f"Selected page ID {selected_page_id} not found in options.")
        await query.edit_message_text(text="Selected page not found. Please try again.")
        # Maybe reshow selection? Or just clear state? Clearing is safer.
        clear_user_state(chat_id)
        return

    # User selected a page, append summary
    await query.edit_message_text(
        text=f"✅ OK. Adding summary to Notion page '{selected_page.title}'..."
    )
    success = await notion_service.append_text_to_page(
        selected_page.id, f"\n\n--- AuditLife Entry ---\n{processing_result.summary}"
    )

    if success:
        await query.edit_message_text(
            text=f"✅ Summary successfully added to Notion page '{selected_page.title}'."
        )
    else:
        await query.edit_message_text(
            text=f"⚠️ Failed to add summary to Notion page '{selected_page.title}'."
        )

    clear_user_state(chat_id)


async def handle_new_page_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles button press for creating a new page."""
    query = update.callback_query
    await query.answer()

    if not update.effective_chat:
        logger.warning("No effective chat in new page callback.")
        return
    chat_id = update.effective_chat.id

    state, stored_data = get_user_state(chat_id)
    pending_data = get_pending_summary_data(chat_id)  # Gets data if state is correct

    # Can be triggered from AWAITING_PAGE_SELECTION or directly if no pages existed
    if (
        state not in [STATE_AWAITING_PAGE_SELECTION, STATE_AWAITING_PAGE_CONFIRMATION]
        or not pending_data
    ):
        # Check if it was triggered because no pages existed initially
        if state == STATE_AWAITING_NEW_PAGE_NAME and pending_data:
            # This state might be set if no pages were found initially
            pass  # Proceed to ask for name
        else:
            logger.warning(f"Received new page callback in unexpected state: {state}")
            await query.edit_message_text(
                text="Your request might have timed out or is out of order. Please send the input again."
            )
            clear_user_state(chat_id)
            return

    # Transition state to wait for the user's text input (the page name)
    set_user_state(
        chat_id, STATE_AWAITING_NEW_PAGE_NAME, stored_data
    )  # Keep data, change state
    await telegram_service.request_new_page_name(update, context)


async def handle_new_page_name_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page_title: str,
    stored_data: dict,
) -> None:
    """Handles the text input after user was prompted for a new page name."""
    if not update.effective_chat:
        logger.warning("No effective chat for new page name input.")
        return
    chat_id = update.effective_chat.id

    if not page_title:
        await telegram_service.reply_text(
            update, context, "Page title cannot be empty. Please provide a name."
        )
        # Keep state as STATE_AWAITING_NEW_PAGE_NAME
        return

    # Reconstruct needed objects from stored dictionaries
    try:
        processing_result = ProcessingResult(**stored_data["processing_result"])
    except Exception as e:
        logger.error(
            f"Failed to reconstruct data from state for new page creation: {e}",
            exc_info=True,
        )
        await telegram_service.reply_text(
            update,
            context,
            "Internal error loading data. Please try creating the page again.",
        )
        clear_user_state(chat_id)
        return

    summary = processing_result.summary

    # Create the new page in Notion
    await telegram_service.reply_text(
        update, context, f"✨ Creating Notion page '{page_title}'..."
    )
    new_page_info = await notion_service.create_notion_page(
        title=page_title, initial_content=f"--- AuditLife Entry ---\n{summary}"
    )

    if new_page_info:
        await telegram_service.reply_text(
            update,
            context,
            f"✅ Successfully created Notion page '{new_page_info.title}' and added the summary.",
        )
    else:
        await telegram_service.reply_text(
            update, context, f"⚠️ Failed to create Notion page '{page_title}'."
        )

    clear_user_state(chat_id)


async def reset_state_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles the /reset command."""
    if not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    clear_user_state(chat_id)
    logger.info(f"State reset requested and performed for chat_id: {chat_id}")
    await telegram_service.reply_text(
        update,
        context,
        "🔄 Bot state has been reset. Any pending actions are cancelled.",
    )
