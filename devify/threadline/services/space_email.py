"""Space-aware policy helpers for the email pipeline."""

from django.conf import settings

from spaces.models import Space


def email_ai_allowed(email) -> bool:
    """Whether an email may enter merge/workflow/AI processing.

    Team spaces are receive-and-read only in the first release: the mail is
    stored and shown to members, but no merge, workflow, Relay delivery or
    LLM call runs for it. Personal-space mail keeps the existing pipeline.
    ``EMAIL_TEAM_AI_ENABLED`` is the explicit switch for a later release.
    """
    if getattr(settings, "EMAIL_TEAM_AI_ENABLED", False):
        return True
    if not getattr(email, "space_id", None):
        return True
    space = email.space
    return not (space and space.kind == Space.Kind.TEAM)
