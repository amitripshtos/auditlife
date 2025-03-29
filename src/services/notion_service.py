import logging
from typing import List, Optional
from notion_client import AsyncClient, APIResponseError, APIErrorCode
from src.config import APP_CONFIG
from src.models import Fact, NotionPageInfo

logger = logging.getLogger(__name__)

# Initialize async Notion client
notion = AsyncClient(auth=APP_CONFIG.notion_api_key)

async def add_facts_to_database(facts: List[Fact], source_text: str) -> bool:
    """Adds extracted facts as new pages/entries to the configured Notion database.

    Args:
        facts: A list of Fact objects to add.
        source_text: The original text from which facts were derived, for context.

    Returns:
        True if all facts were added successfully (or if list was empty), False otherwise.
    """
    if not facts:
        logger.info("No facts provided to add to Notion database.")
        return True

    database_id = APP_CONFIG.notion_facts_database_id
    logger.info(f"Adding {len(facts)} facts to Notion database ID: {database_id}")
    success = True

    for fact in facts:
        # Construct Notion page properties based on the database schema
        # Ensure property names match your Notion DB (configured in AppConfig)
        # We assume 'Title' properties exist for subject, predicate, object
        # and 'Rich Text' for context and source_text. Adjust types as needed.
        properties = {
            APP_CONFIG.notion_db_property_subject: {
                "title": [{"text": {"content": fact.subject}}]
            },
            APP_CONFIG.notion_db_property_predicate: {
                "rich_text": [{"text": {"content": fact.predicate}}]
            },  # Using rich_text for flexibility
            APP_CONFIG.notion_db_property_object: {
                "rich_text": [{"text": {"content": fact.object}}]
            },  # Using rich_text for flexibility
        }
        # Add optional fields if they exist and properties are configured
        if fact.context and APP_CONFIG.notion_db_property_context:
            properties[APP_CONFIG.notion_db_property_context] = {
                "rich_text": [{"text": {"content": fact.context}}]
            }
        if source_text and APP_CONFIG.notion_db_property_source_text:
            # Limit source text length to avoid Notion API limits (e.g., 2000 chars for rich text)
            truncated_source = (
                source_text[:1990] + "..." if len(source_text) > 2000 else source_text
            )
            properties[APP_CONFIG.notion_db_property_source_text] = {
                "rich_text": [{"text": {"content": truncated_source}}]
            }

        try:
            await notion.pages.create(
                parent={"type": "database_id", "database_id": database_id},
                properties=properties,
            )
            logger.debug(
                f"Successfully added fact: {fact.subject} - {fact.predicate} - {fact.object}"
            )
        except APIResponseError as e:
            logger.error(
                f"Notion API error adding fact: {fact}. Error: {e}", exc_info=True
            )
            # Check for specific errors if needed, e.g., schema mismatch
            if e.code == APIErrorCode.ValidationError:
                logger.error(
                    "Validation Error: Check if Notion database properties match config (names and types)."
                )
            success = False
        except Exception as e:
            logger.error(
                f"Unexpected error adding fact to Notion: {fact}. Error: {e}",
                exc_info=True,
            )
            success = False

    logger.info(f"Finished adding facts to Notion. Overall success: {success}")
    return success


async def list_pages_under_parent() -> List[NotionPageInfo]:
    """
    Lists pages that are direct children of the configured NOTION_SUMMARY_PARENT_ID
    using the blocks.children.list endpoint. Filters for child pages.
    Note: Notion API returns children in a fixed order (usually creation order).

    Returns:
        A list of NotionPageInfo objects for the found child pages.
    """
    parent_id = APP_CONFIG.notion_summary_parent_id
    logger.info(f"Listing child pages under Notion parent block ID: {parent_id}")
    pages_info: List[NotionPageInfo] = []
    next_cursor: Optional[str] = None
    has_more: bool = True

    while has_more:
        try:
            # Use blocks.children.list to get children of the parent page/block
            response = await notion.blocks.children.list(
                block_id=parent_id,
                page_size=100, # Request the maximum allowed page size
                start_cursor=next_cursor
            )

            results = response.get("results", [])
            logger.debug(f"Retrieved {len(results)} child blocks (cursor: {next_cursor}).")

            for block in results:
                # We are only interested in blocks of type 'child_page'
                # Other types could be 'paragraph', 'heading_1', 'child_database', etc.
                if block.get("object") == "block" and block.get("type") == "child_page":
                    page_id = block.get("id")
                    # The title for a child_page block is directly available in the response
                    page_title = block.get("child_page", {}).get("title", "Untitled")

                    if page_id:
                        pages_info.append(NotionPageInfo(id=page_id, title=page_title))
                        logger.debug(f"Found child page: ID={page_id}, Title='{page_title}'")
                    else:
                         logger.warning(f"Found child_page block without an ID: {block}")
                # else:
                    # Log other block types if needed for debugging
                    # logger.debug(f"Skipping non-child_page block: Type={block.get('type')}, ID={block.get('id')}")

            # Handle pagination
            has_more = response.get("has_more", False)
            next_cursor = response.get("next_cursor")
            if not has_more:
                logger.debug("No more child blocks to fetch.")
                break # Exit the while loop

        except APIResponseError as e:
            logger.error(f"Notion API error listing children for block {parent_id}: {e}", exc_info=True)
            if e.code == APIErrorCode.ObjectNotFound:
                logger.error(f"Parent block/page with ID '{parent_id}' not found or the integration lacks access.")
            elif e.code == APIErrorCode.ValidationError:
                 logger.error(f"Validation error, likely '{parent_id}' is not a valid block ID.")
            # Stop processing if an error occurs
            has_more = False # Prevent potential infinite loop on persistent error
            # Return empty list or re-raise depending on desired behavior
            return [] # Return empty list on error
        except Exception as e:
            logger.error(f"Unexpected error listing Notion child pages for parent {parent_id}: {e}", exc_info=True)
            has_more = False # Prevent potential infinite loop
            return [] # Return empty list on unexpected error

    logger.info(f"Found {len(pages_info)} child pages under parent {parent_id}.")

    # The API doesn't guarantee order by last edited time here.
    # We might want to sort them alphabetically for consistent display.
    pages_info.sort(key=lambda p: p.title.lower())
    logger.debug(f"Sorted child pages alphabetically: {[p.title for p in pages_info]}")

    return pages_info


async def append_text_to_page(page_id: str, text_to_append: str) -> bool:
    """
    Appends text content as a new paragraph block to a Notion page.

    Args:
        page_id: The ID of the Notion page.
        text_to_append: The text content to add.

    Returns:
        True if successful, False otherwise.
    """
    logger.info(f"Appending text to Notion page ID: {page_id}")
    try:
        # Append as a new paragraph block
        await notion.blocks.children.append(
            block_id=page_id,
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"type": "text", "text": {"content": text_to_append}}
                        ]
                    },
                }
            ],
        )
        logger.info(f"Successfully appended text to page {page_id}.")
        return True
    except APIResponseError as e:
        logger.error(
            f"Notion API error appending text to page {page_id}: {e}", exc_info=True
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error appending text to Notion page {page_id}: {e}",
            exc_info=True,
        )
        return False


async def create_notion_page(
    title: str, initial_content: str
) -> Optional[NotionPageInfo]:
    """
    Creates a new Notion page under the configured parent ID.

    Args:
        title: The title for the new page.
        initial_content: Text to add as the first paragraph block.

    Returns:
        NotionPageInfo of the created page, or None on failure.
    """
    parent_id = APP_CONFIG.notion_summary_parent_id
    logger.info(f"Creating new Notion page '{title}' under parent {parent_id}")

    # Determine parent type (page or database) for the API call
    # This might require fetching the parent object or making an assumption based on configuration
    # Assuming parent is a PAGE for this example. If it's a database, the structure is different.
    parent_structure = {"page_id": parent_id}
    # If parent is a database: parent_structure = {"database_id": parent_id}
    # You might need a config flag or auto-detection logic here.

    # Define the title property structure (usually named 'title')
    # Check your specific Notion setup if this differs.
    title_property_name = "title"  # Default assumption

    try:
        create_response = await notion.pages.create(
            parent=parent_structure,
            properties={
                title_property_name: {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            },
            children=[  # Add initial content as a block
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"type": "text", "text": {"content": initial_content}}
                        ]
                    },
                }
            ],
        )
        page_id = create_response.get("id")
        if page_id:
            logger.info(
                f"Successfully created Notion page: ID={page_id}, Title='{title}'"
            )
            return NotionPageInfo(id=page_id, title=title)
        else:
            logger.error("Notion page creation response did not contain an ID.")
            return None

    except APIResponseError as e:
        logger.error(f"Notion API error creating page '{title}': {e}", exc_info=True)
        if e.code == APIErrorCode.ValidationError:
            logger.error(
                "Validation Error: Check parent ID type (page/database) and title property name."
            )
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error creating Notion page '{title}': {e}", exc_info=True
        )
        return None
