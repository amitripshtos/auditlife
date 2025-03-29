import os
import logging
from dotenv import load_dotenv


logger = logging.getLogger(__name__)


def load_config() -> None:
    """Loads configuration from .env file."""
    load_dotenv()
    logger.info("Configuration loaded from .env file.")


class AppConfig:
    """Application configuration class."""

    def __init__(self):
        load_config()  # Load .env first

        self.telegram_bot_token: str = self._get_env_var("TELEGRAM_BOT_TOKEN")
        allowed_user_ids_str: str = self._get_env_var("ALLOWED_TELEGRAM_USER_IDS")
        self.allowed_telegram_user_ids: list[int] = self._parse_int_list(
            allowed_user_ids_str
        )

        self.openai_api_key: str = self._get_env_var("OPENAI_API_KEY")
        self.openai_model_gpt: str = os.getenv("OPENAI_MODEL_GPT", "gpt-4o")
        self.openai_model_whisper: str = os.getenv("OPENAI_MODEL_WHISPER", "whisper-1")

        self.notion_api_key: str = self._get_env_var("NOTION_API_KEY")
        self.notion_facts_database_id: str = self._get_env_var(
            "NOTION_FACTS_DATABASE_ID"
        )
        # ID of the Notion page/database under which relevant documents for summaries reside
        self.notion_summary_parent_id: str = self._get_env_var(
            "NOTION_SUMMARY_PARENT_ID"
        )

        # Define the expected structure of the Notion Facts Database
        # These should match the *exact* names of your Notion Database properties
        self.notion_db_property_subject: str = os.getenv(
            "NOTION_DB_PROPERTY_SUBJECT", "Subject"
        )
        self.notion_db_property_predicate: str = os.getenv(
            "NOTION_DB_PROPERTY_PREDICATE", "Predicate"
        )
        self.notion_db_property_object: str = os.getenv(
            "NOTION_DB_PROPERTY_OBJECT", "Object"
        )
        self.notion_db_property_context: str = os.getenv(
            "NOTION_DB_PROPERTY_CONTEXT", "Context"
        )
        self.notion_db_property_source_text: str = os.getenv(
            "NOTION_DB_PROPERTY_SOURCE_TEXT", "Source Text"
        )

        if not self.allowed_telegram_user_ids:
            logger.warning(
                "ALLOWED_TELEGRAM_USER_IDS is not set or empty. The bot will respond to anyone."
            )

    def _get_env_var(self, var_name: str) -> str:
        """Gets an environment variable or raises an error if not found."""
        value = os.getenv(var_name)
        if value is None:
            logger.error(f"Environment variable '{var_name}' not found.")
            raise ValueError(f"Missing required environment variable: {var_name}")
        return value

    def _parse_int_list(self, value: str) -> list[int]:
        """Parses a comma-separated string of integers."""
        if not value:
            return []
        try:
            return [int(item.strip()) for item in value.split(",")]
        except ValueError as e:
            logger.error(
                f"Invalid format for integer list in env var: {value}. Error: {e}"
            )
            raise ValueError(f"Invalid format for integer list: {value}")


# Singleton instance
APP_CONFIG = AppConfig()
