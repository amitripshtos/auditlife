from pydantic import BaseModel, Field
from typing import List, Optional


class Fact(BaseModel):
    """
    Represents a single extracted fact.
    Follows a Subject-Predicate-Object structure.
    """

    subject: str = Field(description="The main entity or person the fact is about.")
    predicate: str = Field(
        description="The relationship, action, or attribute connecting the subject and object."
    )
    object: str = Field(
        description="The entity, value, or concept related to the subject via the predicate."
    )
    context: Optional[str] = Field(
        None,
        description="The surrounding sentence or phrase providing context for the fact.",
    )


class ProcessingResult(BaseModel):
    """Holds the results after processing text input."""

    original_text: str
    english_text: str
    facts: List[Fact]
    summary: str


class NotionPageInfo(BaseModel):
    """Basic information about a Notion page."""

    id: str
    title: str
