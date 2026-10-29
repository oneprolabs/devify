import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from chat_domain.models import Conversation
from spaces.models import Space


class AnalysisJob(models.Model):
    """A resumable extraction job over a fixed window of an upload batch."""

    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        READY = "ready", "Ready"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="chat_analysis_jobs",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chat_analysis_jobs",
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.PROTECT,
        related_name="chat_analysis_jobs",
    )
    request_key = models.CharField(max_length=255)
    start_seq = models.PositiveBigIntegerField(default=0)
    end_seq = models.PositiveBigIntegerField()
    input_version = models.CharField(max_length=100)
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.QUEUED,
    )
    checkpoint = models.JSONField(default=dict, blank=True)
    specification = models.JSONField(default=dict, blank=True)
    result_ref = models.JSONField(null=True, blank=True)
    lease_owner = models.CharField(max_length=200, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    fencing_token = models.PositiveBigIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("space", "request_key"),
                name="unique_chat_analysis_request",
            ),
        ]
        indexes = [
            models.Index(fields=("space", "state")),
            models.Index(fields=("conversation", "end_seq", "state")),
        ]

    def clean(self):
        if self.end_seq < self.start_seq:
            raise ValidationError(
                {
                    "end_seq": (
                        "end_seq must be greater than or equal to start_seq."
                    )
                }
            )
        if (
            self.conversation_id
            and self.space_id
            and self.conversation.space_id != self.space_id
        ):
            raise ValidationError(
                {"conversation": "Conversation must belong to the space."}
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.request_key} ({self.state})"


class Note(models.Model):
    """A stage summary backed by uploaded messages, not an event."""

    class Origin(models.TextChoices):
        AUTO = "auto", "Auto"
        MANUAL = "manual", "Manual"

    class AssignmentMode(models.TextChoices):
        AUTO = "auto", "Auto"
        MANUAL = "manual", "Manual"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="chat_notes",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chat_notes",
    )
    analysis_job = models.ForeignKey(
        AnalysisJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notes",
    )
    note_key = models.CharField(max_length=255)
    title = models.CharField(max_length=500)
    content = models.TextField()
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    origin = models.CharField(
        max_length=20,
        choices=Origin.choices,
        default=Origin.AUTO,
    )
    assignment_mode = models.CharField(
        max_length=20,
        choices=AssignmentMode.choices,
        default=AssignmentMode.AUTO,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-start_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("space", "note_key"),
                name="unique_chat_note_key",
            ),
        ]
        indexes = [
            models.Index(fields=("space", "start_at", "id")),
            models.Index(fields=("analysis_job", "id")),
            models.Index(fields=("space", "assignment_mode", "id")),
        ]

    def clean(self):
        if self.end_at and not self.start_at:
            raise ValidationError(
                {"end_at": "end_at requires a business start time."}
            )
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValidationError(
                {"end_at": "end_at must be greater than or equal to start_at."}
            )
        if (
            self.analysis_job_id
            and self.space_id
            and self.analysis_job.space_id != self.space_id
        ):
            raise ValidationError(
                {"analysis_job": "Analysis job must belong to the same space."}
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class NoteEvidence(models.Model):
    """A Note's reference to the original message or message part."""

    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="evidence",
    )
    message = models.ForeignKey(
        "chat_domain.Message",
        on_delete=models.CASCADE,
        related_name="chat_note_evidence",
    )
    message_part = models.ForeignKey(
        "chat_domain.MessagePart",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_note_evidence",
    )
    reference_key = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("note", "reference_key"),
                name="unique_chat_note_evidence_reference",
            ),
        ]
        indexes = [
            models.Index(fields=("message", "note")),
            models.Index(fields=("message_part", "note")),
        ]

    @staticmethod
    def build_reference_key(message_id, message_part_id=None):
        return f"{message_id}:{message_part_id or 'whole'}"

    def clean(self):
        if not self.message_id:
            raise ValidationError({"message": "message is required."})
        if (
            self.note_id
            and self.message.conversation.space_id != self.note.space_id
        ):
            raise ValidationError(
                {"message": "Evidence must belong to the same space."}
            )
        if (
            self.message_part_id
            and self.message_part.message_id != self.message_id
        ):
            raise ValidationError(
                {"message_part": "Message part must belong to the message."}
            )

    def save(self, *args, **kwargs):
        if self.message_id:
            self.reference_key = self.build_reference_key(
                self.message_id, self.message_part_id
            )
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.reference_key


class Event(models.Model):
    """A tracked matter that aggregates Notes."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="chat_events",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chat_events",
    )
    event_key = models.CharField(max_length=255)
    title = models.CharField(max_length=500)
    content = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        null=True,
        blank=True,
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_activity_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("space", "event_key"),
                name="unique_chat_event_key",
            ),
        ]
        indexes = [
            models.Index(fields=("space", "status", "last_activity_at", "id")),
            models.Index(fields=("space", "last_activity_at", "id")),
        ]

    def __str__(self):
        return self.title


class EventNote(models.Model):
    """Current membership of a Note in an Event."""

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="note_links",
    )
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="event_links",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chat_event_note_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("event", "note"),
                name="unique_chat_event_note",
            ),
        ]
        indexes = [
            models.Index(fields=("note", "event")),
        ]

    def clean(self):
        if (
            self.event_id
            and self.note_id
            and self.event.space_id != self.note.space_id
        ):
            raise ValidationError(
                {"note": "Note and event must belong to the same space."}
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class EventRelation(models.Model):
    """A stored judgement about the relation between two Events.

    Pairs are stored in canonical id order, so ``depends_on`` records that a
    dependency exists between the two events, not its direction.
    """

    class RelationKind(models.TextChoices):
        SAME = "same", "Same event"
        RELATED = "related", "Related"
        SEPARATE = "separate", "Separate"
        DEPENDS_ON = "depends_on", "Depends on"

    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="chat_event_relations",
    )
    left_event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="relations_as_left",
    )
    right_event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="relations_as_right",
    )
    relation_kind = models.CharField(
        max_length=20,
        choices=RelationKind.choices,
    )
    decision = models.CharField(
        max_length=20,
        choices=Decision.choices,
        default=Decision.PENDING,
    )
    reason = models.TextField(blank=True)
    source_note_ids = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chat_event_relations",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_chat_event_relations",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("space", "left_event", "right_event"),
                name="unique_chat_event_relation",
            ),
            models.CheckConstraint(
                condition=models.Q(left_event__lt=models.F("right_event")),
                name="chat_event_relation_ordered",
            ),
        ]
        indexes = [
            models.Index(fields=("space", "decision")),
            models.Index(fields=("right_event", "decision")),
        ]

    def _order_events(self):
        if (
            self.left_event_id
            and self.right_event_id
            and self.left_event_id > self.right_event_id
        ):
            self.left_event_id, self.right_event_id = (
                self.right_event_id,
                self.left_event_id,
            )
            self._state.fields_cache.pop("left_event", None)
            self._state.fields_cache.pop("right_event", None)

    def clean(self):
        self._order_events()
        if self.left_event_id and self.right_event_id:
            if self.left_event_id == self.right_event_id:
                raise ValidationError(
                    {"right_event": "An event cannot be related to itself."}
                )
            space_ids = {
                self.left_event.space_id,
                self.right_event.space_id,
            }
            if self.space_id and space_ids != {self.space_id}:
                raise ValidationError(
                    {"space": "Related events must belong to the same space."}
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.left_event_id}-{self.right_event_id}:"
            f"{self.relation_kind}"
        )
