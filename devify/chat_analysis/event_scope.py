"""Rules shared by event extraction and publication-time grouping."""

import re

SAME_MATTER_RULE = (
    "Treat steps as one matter when cited messages explicitly show that they "
    "advance the same concrete outcome or acceptance goal (for example, "
    "fixing, packaging and retesting as part of one identified release). "
    "Keep independently owned or independently accepted deliverables, "
    "distinct releases and repeated occurrences separate. The same product, "
    "version number, conversation, people or nearby dates alone are not "
    "enough. Links such as a quoted message, a concrete identifier or an "
    "explicit statement of the shared goal are evidence, not automatic "
    "merges. "
    "When multiple targets fit and there is no clear match, do not attach. "
)

_RELEASE_VERSION = re.compile(
    r"(?:发布|发版|版本|release\b|version\b)\s*[:：#-]?\s*v?"
    r"(?P<version>\d+(?:\.\d+){1,3})(?![0-9.])",
    re.IGNORECASE,
)


def release_versions(text):
    """Return explicitly labeled versions, not arbitrary version mentions."""
    return {
        match['version'] for match in _RELEASE_VERSION.finditer(text or '')
    }
