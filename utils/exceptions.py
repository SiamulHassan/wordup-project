"""Domain-specific failures surfaced safely to the GUI."""


class WordUpImporterError(RuntimeError):
    """Base class for expected application failures."""


class WordUpNotFoundError(WordUpImporterError):
    """No matching WordUp window was found."""


class SearchControlNotFoundError(WordUpImporterError):
    """The WordUp search affordance or edit control could not be found."""


class WordNotFoundError(WordUpImporterError):
    """No exact result matched the requested word."""


class WordMismatchError(WordUpImporterError):
    """The open detail headword does not match the requested word."""


class ShouldLearnButtonNotFoundError(WordUpImporterError):
    """The safe target action could not be identified."""


class AutomationTimeoutError(WordUpImporterError):
    """A detected UI transition did not complete before its timeout."""


class OCRFailureError(WordUpImporterError):
    """OCR was unavailable or failed for a tile."""


class UnsafeAutomationError(WordUpImporterError):
    """Automation safety preconditions were not satisfied."""
