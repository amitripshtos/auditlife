# Audit Life

AuditLife is a personal backend system designed to help you capture, process, and organize information from your daily life, conversations, and thoughts. It uses Telegram as the primary interface, leverages AI for audio transcription and text analysis (OpenAI Whisper & GPT), and stores structured data and summaries in Notion.

## Motivation

In a world full of information and interactions, it's easy to lose track of important details, insights gained from conversations, or commitments made. AuditLife aims to solve this by providing a seamless way to:

* **Capture Fleeting Thoughts:** Quickly record voice notes or send text messages via Telegram.
* **Process Information:** Automatically transcribe audio, translate content to English, extract key facts (especially about people and relationships), and generate concise summaries using AI. Summarize data for AI to consume later as a knowledge graph.
* **Organize Knowledge:** Store extracted facts in a structured Notion database and append summaries to relevant Notion pages, building a personal knowledge base over time.
* **Reduce Manual Effort:** Automate the transcription, analysis, and documentation process, saving time and ensuring valuable information isn't lost.

## Features

* **Telegram Interface:** Interact with the backend using text messages or voice notes through a private Telegram bot.
* **User Authorization:** Configurable access control, ensuring only specified Telegram user IDs can interact with the bot.
* **Audio Transcription:** Uses OpenAI Whisper to transcribe audio recordings (supports multiple languages like English and Hebrew).
* **Text Processing (AI):**
  * Translates transcribed text to English.
  * Extracts structured facts (Subject-Predicate-Object) using OpenAI's GPT models (e.g., GPT-4o).
  * Generates concise summaries of the input.
* **Notion Integration:**
  * Adds extracted facts to a designated Notion database.
  * Intelligently suggests a relevant Notion page for appending the summary.
  * Allows user confirmation, selection from existing pages, or creation of new pages via Telegram inline buttons.
* **State Management:** Handles multi-step interactions (like page selection) gracefully.
* **Reset Functionality:** A `/reset` command to clear any pending bot state for the user.

## Prerequisites

* **Python:** Version 3.12 or higher.
* **pip:** Python package installer (usually included with Python).
* **Git:** (Optional) For cloning the repository.
* **API Keys & IDs:**
  * **Telegram Bot Token:** Obtainable from BotFather on Telegram.
  * **Your Telegram User ID:** You can get this from bots like `@userinfobot`.
  * **OpenAI API Key:** From your OpenAI account dashboard.
  * **Notion API Key (Integration Token):** Create a Notion integration ([https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)) and get the "Internal Integration Token".
  * **Notion Database ID:** Create a database in Notion for storing facts. Share it with your integration. The ID is the long string in the database URL (`https://www.notion.so/your-workspace/DATABASE_ID?v=...`).
  * **Notion Parent Page ID:** Choose an existing Notion page under which summary pages should be listed or created. Share this page (and its children, if necessary) with your integration. The ID is the long string at the end of the page URL (`https://www.notion.so/your-workspace/PAGE_TITLE-PAGE_ID`).

## Installation

1. **Clone the Repository (or Download Files):**

    ```bash
    git clone https://github.com/amitripshtos/auditlife
    cd auditlife
    ```

2. **Create and Activate a Virtual Environment:**

    ```bash
    # Linux/macOS
    python3 -m venv venv
    source venv/bin/activate

    # Windows (Git Bash or WSL)
    python -m venv venv
    source venv/Scripts/activate
    # Windows (Command Prompt)
    python -m venv venv
    .\venv\Scripts\activate
    ```

3. **Install Dependencies:**
    This project uses `uv` and `ruff`.

    ```bash
    uv install
    ```

## Configuration

Configuration is handled via environment variables loaded from a `.env` file in the project's root directory.

1. **Create the `.env` file:**
    Create a file named `.env` in the `auditlife/` directory (alongside `main.py` and `requirements.txt`).

2. **Populate `.env` with your credentials:**
    Copy the following structure into your `.env` file and replace the placeholder values with your actual keys and IDs.

    ```dotenv
    # .env - Fill in your actual values

    # Telegram
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    # Comma-separated list of numeric Telegram User IDs allowed to use the bot
    ALLOWED_TELEGRAM_USER_IDS="YOUR_USER_ID_1,YOUR_USER_ID_2" # e.g., 123456789 or 123456789,987654321

    # OpenAI
    OPENAI_API_KEY="sk-..."
    # Optional: Override default models if needed
    # OPENAI_MODEL_GPT="gpt-4o"
    # OPENAI_MODEL_WHISPER="whisper-1"

    # Notion
    NOTION_API_KEY="secret_..."
    # The Database ID where facts will be stored
    NOTION_FACTS_DATABASE_ID="YOUR_NOTION_DATABASE_ID"
    # The Page ID under which your target summary pages exist/will be created
    NOTION_SUMMARY_PARENT_ID="YOUR_NOTION_PARENT_PAGE_ID"

    # Optional: Override Notion database property names if they differ from defaults
    # Ensure these *exactly* match the property names in your Notion Facts Database
    # Defaults are: "Subject", "Predicate", "Object", "Context", "Source Text"
    # NOTION_DB_PROPERTY_SUBJECT="Subject Name" # Must be a 'Title' property type in Notion
    # NOTION_DB_PROPERTY_PREDICATE="Relation Type" # Should be 'Rich Text' or similar
    # NOTION_DB_PROPERTY_OBJECT="Value Detail" # Should be 'Rich Text' or similar
    # NOTION_DB_PROPERTY_CONTEXT="Source Sentence" # Should be 'Rich Text' or similar
    # NOTION_DB_PROPERTY_SOURCE_TEXT="Original Input" # Should be 'Rich Text' or similar
    ```

3. **Notion Permissions:**
    * Go to the Notion database you specified for `NOTION_FACTS_DATABASE_ID`. Click the `...` menu -> "Add connections" (or "Share" -> Invite) and select your integration. Ensure it has permission to "Insert content".
    * Go to the Notion page you specified for `NOTION_SUMMARY_PARENT_ID`. Click the `...` menu -> "Add connections" (or "Share" -> Invite) and select your integration. Ensure it has permission to "Read content", "Insert content", and potentially "Edit content" (if it needs to manage child pages beyond just reading them). Granting access to the parent page usually allows access to create child pages underneath it.

4. **Notion Database Structure:**
    Ensure your "Facts" database (`NOTION_FACTS_DATABASE_ID`) has columns (properties) that match the names defined in your `.env` file (or the defaults). The default expected types are:
    * `Subject`: **Title**
    * `Predicate`: **Rich Text**
    * `Object`: **Rich Text**
    * `Context`: **Rich Text**
    * `Source Text`: **Rich Text**

## Running the Bot

1. **Ensure your virtual environment is activated.** (You should see `(venv)` at the start of your terminal prompt).
2. **Navigate to the project's root directory** (`auditlife/`) if you aren't already there.
3. **Run the main script:**

    ```bash
    python main.py
    ```

4. The bot will start polling for updates. You should see log messages in your console indicating it's running. Keep the terminal window open while the bot is running. To stop the bot, press `Ctrl+C` in the terminal.

## Usage

Interact with your bot on Telegram:

* **/start:** Sends a welcome message.
* **Text Messages:** Send any text message. The bot will process it to extract facts, generate a summary, add facts to Notion, and prompt you to choose where to save the summary in Notion.
* **Voice Notes / Audio Files:** Send a voice note or upload an audio file (like `.ogg`, `.mp3`, `.wav`). The bot will transcribe it, then process the transcription like a text message.
* **New Page Name:** If you choose to create a new page, the bot will ask you to type the desired page name in the chat.
* **/reset:** If the bot seems stuck in a state (e.g., waiting for a page name you don't want to provide), use this command to cancel the current operation and reset its state for your chat.
