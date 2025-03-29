import logging
import json
from typing import Optional
from openai import AsyncOpenAI, OpenAIError
from src.config import APP_CONFIG
from src.models import Fact, ProcessingResult

logger = logging.getLogger(__name__)

# Initialize async client
aclient = AsyncOpenAI(api_key=APP_CONFIG.openai_api_key)


async def transcribe_audio(audio_file_path: str) -> Optional[str]:
    """
    Transcribes audio using OpenAI Whisper. Detects language automatically.
    Args:
        audio_file_path: Path to the audio file (e.g., .ogg, .mp3, .wav).
    Returns:
        The transcribed text, or None if an error occurred.
    """
    logger.info(f"Transcribing audio file: {audio_file_path}")
    try:
        with open(audio_file_path, "rb") as audio_file:
            # Use the async client's transcription method
            transcript = await aclient.audio.transcriptions.create(
                model=APP_CONFIG.openai_model_whisper,
                file=audio_file,
                # language="en" # Optional: Specify if needed, but Whisper is good at auto-detect
                response_format="text",  # Get plain text directly
            )
        # The response for 'text' format is directly the string
        logger.info("Transcription successful.")
        logger.debug(f"Transcription result: {transcript[:100]}...")  # Log truncated
        # Ensure the result is a string, handle potential None or unexpected types
        return str(transcript) if isinstance(transcript, str) else None
    except OpenAIError as e:
        logger.error(f"OpenAI API error during transcription: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during transcription: {e}", exc_info=True
        )
        return None


async def process_text_with_llm(original_text: str) -> Optional[ProcessingResult]:
    """
    Processes the input text using an LLM (e.g., GPT-4o) to:
    1. Translate to English (if necessary).
    2. Extract structured facts (Subject-Predicate-Object).
    3. Generate a concise summary.

    Args:
        original_text: The text input (can be from transcription or direct message).

    Returns:
        A ProcessingResult object containing english text, facts, and summary, or None on failure.
    """
    logger.info("Processing text with LLM...")

    # Define the desired JSON structure for facts
    fact_schema = Fact.model_json_schema()
    facts_output_format = {"type": "array", "items": fact_schema}

    system_prompt = f"""
You are an AI assistant helping a user audit their life. Your tasks are to:
1.  Analyze the user's input text.
2.  Ensure the core meaning is represented in English. If the input is already English, keep it. If it's another language (like Hebrew), translate its meaning accurately to English.
3.  Extract key facts and important information from the English text. Facts should represent relationships or attributes, primarily focusing on people or important entities. Structure each fact as a JSON object with keys 'subject', 'predicate', and 'object'. Optionally include a 'context' string with the surrounding phrase.
4.  Generate a very concise, clear summary of the English text, capturing the main points without extra words.

Respond with a single JSON object containing three keys:
- "english_text": The English version of the input text.
- "facts": A JSON array of extracted fact objects matching the schema: {json.dumps(facts_output_format)}. If no facts are found, return an empty array [].
- "summary": A string containing the concise summary.
"""

    user_prompt = f"Process the following text:\n\n{original_text}"

    try:
        response = await aclient.chat.completions.create(
            model=APP_CONFIG.openai_model_gpt,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},  # Use JSON mode
            temperature=0.2,  # Lower temperature for more deterministic results
        )

        content = response.choices[0].message.content
        if not content:
            logger.error("LLM returned empty content.")
            return None

        logger.debug(f"LLM raw response content: {content}")

        # Parse the JSON response
        try:
            result_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to decode LLM JSON response: {e}. Response: {content}"
            )
            # Fallback: Try to extract summary even if JSON is broken
            # This is a basic fallback, more robust parsing could be added
            summary_fallback = (
                content.split('"summary": "')[-1].split('"')[0]
                if '"summary": "' in content
                else "Summary extraction failed."
            )
            return ProcessingResult(
                original_text=original_text,
                english_text="Translation/Fact extraction failed.",
                facts=[],
                summary=summary_fallback,
            )

        # Validate and create Pydantic models
        english_text = result_data.get(
            "english_text", original_text
        )  # Fallback to original if missing
        summary = result_data.get("summary", "Summary not generated.")
        raw_facts = result_data.get("facts", [])
        facts = []
        if isinstance(raw_facts, list):
            for fact_data in raw_facts:
                try:
                    # Only include facts with all required fields
                    if isinstance(fact_data, dict) and all(
                        k in fact_data for k in ["subject", "predicate", "object"]
                    ):
                        facts.append(Fact(**fact_data))
                    else:
                        logger.warning(f"Skipping invalid fact data: {fact_data}")
                except Exception as e:  # Catch Pydantic validation errors or others
                    logger.warning(
                        f"Failed to parse fact data: {fact_data}. Error: {e}"
                    )
        else:
            logger.warning(f"LLM returned 'facts' not as a list: {raw_facts}")

        logger.info(
            f"LLM processing successful. Extracted {len(facts)} facts. Summary generated."
        )
        return ProcessingResult(
            original_text=original_text,
            english_text=english_text,
            facts=facts,
            summary=summary,
        )

    except OpenAIError as e:
        logger.error(f"OpenAI API error during LLM processing: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during LLM processing: {e}", exc_info=True
        )
        return None
