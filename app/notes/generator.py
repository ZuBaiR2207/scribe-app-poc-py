"""Note generator port: anything that can turn a transcript into a draft note."""

from typing import Protocol


class NoteGenerationError(Exception):
    """The draft note could not be produced. The message is safe to show to the user."""


class NoteGenerator(Protocol):
    def generate(self, transcript: str) -> str:
        """Return a draft note for the transcript. Raise NoteGenerationError on failure."""
        ...
