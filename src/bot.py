import logging
from telegram.ext import Application, ApplicationBuilder, Defaults
from telegram.constants import ParseMode

from src.config import APP_CONFIG
from src.handlers import HANDLERS, error_handler

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Set higher logging level for httpx to avoid excessive noise
logging.getLogger("httpx").setLevel(logging.WARNING)
# Set higher logging level for specific noisy libraries if needed
# logging.getLogger('telegram.vendor.ptb_urllib3.urllib3').setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def create_application() -> Application:
    """Creates and configures the Telegram Bot Application."""
    logger.info("Creating Telegram Application...")

    # Set default parse mode for messages
    defaults = Defaults(parse_mode=ParseMode.HTML)

    application = (
        ApplicationBuilder()
        .token(APP_CONFIG.telegram_bot_token)
        .defaults(defaults)
        .build()
    )

    # Register all handlers from the handlers module
    for handler in HANDLERS:
        application.add_handler(handler)

    # Register the error handler
    application.add_error_handler(error_handler)

    logger.info("Telegram Application created and handlers registered.")
    return application


def run_bot(application: Application) -> None:
    """Starts the polling process for the bot."""
    logger.info("Starting bot polling...")
    # Run the bot until the user presses Ctrl-C
    application.run_polling()
    logger.info("Bot polling stopped.")
