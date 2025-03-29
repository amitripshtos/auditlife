import logging
from src.bot import create_application, run_bot
from src.config import APP_CONFIG

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting AuditLife Bot...")
    try:
        logger.info(
            f"Bot configured for user IDs: {APP_CONFIG.allowed_telegram_user_ids}"
        )
        logger.info(f"Notion Facts DB: {APP_CONFIG.notion_facts_database_id}")
        logger.info(f"Notion Summary Parent: {APP_CONFIG.notion_summary_parent_id}")

        app = create_application()
        run_bot(app)
    except ValueError as e:
        # Catch configuration errors specifically
        logger.critical(f"Configuration error: {e}. Please check your .env file.")
    except Exception as e:
        logger.critical(f"Failed to start the bot: {e}", exc_info=True)
