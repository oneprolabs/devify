from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_analysis.api_serializers import (
    EventCreateSerializer,
    EventNoteSerializer,
    EventRelationCreateSerializer,
    EventRelationSerializer,
    EventSerializer,
    EventUpdateSerializer,
    EvidenceCreateSerializer,
    NoteCreateSerializer,
    NoteEvidenceSerializer,
    NoteSerializer,
    NoteUpdateSerializer,
)
from chat_analysis.models import Event, EventNote, EventRelation, Note
from chat_analysis.services import (
    ChatAnalysisError,
    ChatAnalysisConflict,
    ChatAnalysisPermissionError,
    add_note_evidence,
    assign_note_events,
    create_event,
    create_note,
    delete_event,
    delete_note,
    upsert_event_relation,
)
from chat_domain.models import Message, MessagePart
from spaces.models import Space, SpaceMembership, SpaceTakeover
from spaces.services import SpacePermissionService, audit_space_action


class AnalysisPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


def _authorized_space(user, space_id, *, write=False):
    space = get_object_or_404(Space, pk=space_id)
    allowed = (
        SpacePermissionService.can_upload(user, space)
        if write
        else SpacePermissionService.can_read(user, space)
    )
    if not allowed:
        return None, None
    takeover = None
    if getattr(user, "is_staff", False):
        takeover = SpaceTakeover.objects.filter(
            space=space, admin=user, active=True
        ).first()
    return space, takeover


def _pagination_data(paginator):
    return {
        "total": paginator.page.paginator.count,
        "page": paginator.page.number,
        "page_size": paginator.get_page_size(paginator.request),
        "next": paginator.get_next_link(),
        "previous": paginator.get_previous_link(),
    }


def _editable(actor, instance):
    if getattr(actor, "is_staff", False):
        return SpacePermissionService.has_active_takeover(
            actor, instance.space
        )
    membership = SpacePermissionService.membership(actor, instance.space)
    return bool(
        membership
        and membership.status == SpaceMembership.Status.ACTIVE
        and (
            SpacePermissionService.can_manage(membership)
            or instance.created_by_id == actor.pk
        )
    )


class SpaceNoteListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        notes = Note.objects.filter(space=space).order_by("-start_at", "-id")
        origin = request.query_params.get("origin")
        if origin:
            notes = notes.filter(origin=origin)
        paginator = AnalysisPagination()
        page = paginator.paginate_queryset(notes, request, view=self)
        data = NoteSerializer(page, many=True).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.note_list_viewed",
                resource_type="note",
                metadata={"takeover_id": takeover.pk},
            )
        return Response(
            {
                "data": {
                    "list": data,
                    "pagination": _pagination_data(paginator),
                }
            }
        )

    @transaction.atomic
    def post(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id, write=True)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        serializer = NoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        analysis_job = None
        if values.get("analysis_job_id"):
            analysis_job = space.chat_analysis_jobs.filter(
                pk=values["analysis_job_id"]
            ).first()
            if analysis_job is None:
                return Response(
                    {"detail": "Analysis job not found."}, status=404
                )
        try:
            note = create_note(
                actor=request.user,
                space=space,
                note_key=values["note_key"],
                title=values["title"],
                content=values["content"],
                origin=Note.Origin.MANUAL,
                start_at=values.get("start_at"),
                end_at=values.get("end_at"),
                analysis_job=analysis_job,
            )
        except ChatAnalysisPermissionError as error:
            return Response({"detail": str(error)}, status=403)
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.note_created",
            resource_type="note",
            resource_id=note.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response({"data": NoteSerializer(note).data}, status=201)


class NoteDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, note_id):
        note = get_object_or_404(
            Note.objects.select_related("space"), pk=note_id
        )
        space, takeover = _authorized_space(request.user, note.space_id)
        if space is None:
            return Response({"detail": "Note not found."}, status=404)
        data = NoteSerializer(note).data
        data["evidence"] = NoteEvidenceSerializer(
            note.evidence.all(), many=True
        ).data
        data["event_ids"] = list(
            note.event_links.order_by("id").values_list("event_id", flat=True)
        )
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.note_viewed",
                resource_type="note",
                resource_id=note.pk,
                metadata={"takeover_id": takeover.pk},
            )
        return Response({"data": data})

    @transaction.atomic
    def patch(self, request, note_id):
        note = get_object_or_404(
            Note.objects.select_related("space"), pk=note_id
        )
        space, takeover = _authorized_space(
            request.user, note.space_id, write=True
        )
        if space is None:
            return Response({"detail": "Note not found."}, status=404)
        if not _editable(request.user, note):
            return Response(
                {"detail": "Note edit permission required."}, status=403
            )
        serializer = NoteUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(note, field, value)
        note.save()
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.note_updated",
            resource_type="note",
            resource_id=note.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response({"data": NoteSerializer(note).data})

    @transaction.atomic
    def delete(self, request, note_id):
        note = get_object_or_404(
            Note.objects.select_related("space"), pk=note_id
        )
        space, takeover = _authorized_space(
            request.user, note.space_id, write=True
        )
        if space is None:
            return Response({"detail": "Note not found."}, status=404)
        try:
            delete_note(actor=request.user, note=note)
        except ChatAnalysisPermissionError as error:
            return Response({"detail": str(error)}, status=403)
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.note_deleted",
            resource_type="note",
            resource_id=note_id,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response(status=204)


class NoteEvidenceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, note_id):
        note = get_object_or_404(
            Note.objects.select_related("space"), pk=note_id
        )
        space, takeover = _authorized_space(
            request.user, note.space_id, write=True
        )
        if space is None:
            return Response({"detail": "Note not found."}, status=404)
        serializer = EvidenceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        message = get_object_or_404(
            Message.objects.filter(conversation__space=space),
            pk=values["message_id"],
        )
        message_part = None
        if values.get("message_part_id"):
            message_part = get_object_or_404(
                MessagePart.objects.filter(message=message),
                pk=values["message_part_id"],
            )
        try:
            evidence = add_note_evidence(
                actor=request.user,
                note=note,
                message=message,
                message_part=message_part,
            )
        except ChatAnalysisPermissionError as error:
            return Response({"detail": str(error)}, status=403)
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.note_evidence_added",
            resource_type="note",
            resource_id=note.pk,
            metadata={
                "message_id": message.pk,
                "takeover_id": takeover.pk if takeover else None,
            },
        )
        return Response(
            {"data": NoteEvidenceSerializer(evidence).data}, status=201
        )


class SpaceEventListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        events = Event.objects.filter(space=space).order_by(
            "-last_activity_at", "-id"
        )
        state = request.query_params.get("status")
        if state:
            events = events.filter(status=state)
        paginator = AnalysisPagination()
        page = paginator.paginate_queryset(events, request, view=self)
        data = EventSerializer(page, many=True).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.event_list_viewed",
                resource_type="event",
                metadata={"takeover_id": takeover.pk},
            )
        return Response(
            {
                "data": {
                    "list": data,
                    "pagination": _pagination_data(paginator),
                }
            }
        )

    @transaction.atomic
    def post(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id, write=True)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            event = create_event(
                actor=request.user, space=space, **serializer.validated_data
            )
        except ChatAnalysisPermissionError as error:
            return Response({"detail": str(error)}, status=403)
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.event_created",
            resource_type="event",
            resource_id=event.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response({"data": EventSerializer(event).data}, status=201)


class EventDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        event = get_object_or_404(
            Event.objects.select_related("space"), pk=event_id
        )
        space, takeover = _authorized_space(request.user, event.space_id)
        if space is None:
            return Response({"detail": "Event not found."}, status=404)
        data = EventSerializer(event).data
        data["note_ids"] = list(
            event.note_links.order_by("id").values_list("note_id", flat=True)
        )
        data["relation_ids"] = list(
            EventRelation.objects.filter(space=space)
            .filter(left_event=event)
            .values_list("id", flat=True)
        ) + list(
            EventRelation.objects.filter(
                space=space, right_event=event
            ).values_list("id", flat=True)
        )
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.event_viewed",
                resource_type="event",
                resource_id=event.pk,
                metadata={"takeover_id": takeover.pk},
            )
        return Response({"data": data})

    @transaction.atomic
    def patch(self, request, event_id):
        event = get_object_or_404(
            Event.objects.select_related("space"), pk=event_id
        )
        space, takeover = _authorized_space(
            request.user, event.space_id, write=True
        )
        if space is None:
            return Response({"detail": "Event not found."}, status=404)
        if not _editable(request.user, event):
            return Response(
                {"detail": "Event edit permission required."}, status=403
            )
        serializer = EventUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(event, field, value)
        event.last_activity_at = event.last_activity_at or timezone.now()
        event.save()
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.event_updated",
            resource_type="event",
            resource_id=event.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response({"data": EventSerializer(event).data})

    @transaction.atomic
    def delete(self, request, event_id):
        event = get_object_or_404(
            Event.objects.select_related("space"), pk=event_id
        )
        space, takeover = _authorized_space(
            request.user, event.space_id, write=True
        )
        if space is None:
            return Response({"detail": "Event not found."}, status=404)
        try:
            delete_event(actor=request.user, event=event)
        except ChatAnalysisPermissionError as error:
            return Response({"detail": str(error)}, status=403)
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.event_deleted",
            resource_type="event",
            resource_id=event_id,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response(status=204)


class EventNotesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, event_id):
        event = get_object_or_404(
            Event.objects.select_related("space"), pk=event_id
        )
        space, takeover = _authorized_space(
            request.user, event.space_id, write=True
        )
        if space is None:
            return Response({"detail": "Event not found."}, status=404)
        serializer = EventNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notes = list(
            Note.objects.filter(
                space=space,
                pk__in=serializer.validated_data["note_ids"],
            )
        )
        if len(notes) != len(set(serializer.validated_data["note_ids"])):
            return Response(
                {"detail": "One or more notes were not found."}, status=404
            )
        try:
            (
                assign_note_events(
                    actor=request.user,
                    note=notes[0],
                    events=[event],
                    manual=True,
                )
                if len(notes) == 1
                else None
            )
            if len(notes) != 1:
                for note in notes:
                    assign_note_events(
                        actor=request.user,
                        note=note,
                        events=[event],
                        manual=True,
                    )
        except ChatAnalysisPermissionError as error:
            return Response({"detail": str(error)}, status=403)
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.event_notes_assigned",
            resource_type="event",
            resource_id=event.pk,
            metadata={
                "note_ids": [note.pk for note in notes],
                "takeover_id": takeover.pk if takeover else None,
            },
        )
        return Response(
            {
                "data": {
                    "event_id": event.pk,
                    "note_ids": [note.pk for note in notes],
                }
            }
        )

    @transaction.atomic
    def delete(self, request, event_id, note_id):
        event = get_object_or_404(
            Event.objects.select_related("space"), pk=event_id
        )
        space, takeover = _authorized_space(
            request.user, event.space_id, write=True
        )
        if space is None:
            return Response({"detail": "Event not found."}, status=404)
        note = get_object_or_404(Note, space=space, pk=note_id)
        if not _editable(request.user, note):
            return Response(
                {"detail": "Note edit permission required."}, status=403
            )
        deleted, _ = EventNote.objects.filter(event=event, note=note).delete()
        if not deleted:
            return Response(
                {"detail": "Event note link not found."}, status=404
            )
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.event_note_unassigned",
            resource_type="event",
            resource_id=event.pk,
            metadata={
                "note_id": note.pk,
                "takeover_id": takeover.pk if takeover else None,
            },
        )
        return Response(status=204)


class SpaceEventRelationListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        relations = EventRelation.objects.filter(space=space).order_by(
            "-updated_at", "-id"
        )
        paginator = AnalysisPagination()
        page = paginator.paginate_queryset(relations, request, view=self)
        data = EventRelationSerializer(page, many=True).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.event_relation_list_viewed",
                resource_type="event_relation",
                metadata={"takeover_id": takeover.pk},
            )
        return Response(
            {
                "data": {
                    "list": data,
                    "pagination": _pagination_data(paginator),
                }
            }
        )

    @transaction.atomic
    def post(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id, write=True)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        serializer = EventRelationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        events = list(
            Event.objects.filter(
                space=space,
                pk__in=(values["left_event_id"], values["right_event_id"]),
            )
        )
        if len(events) != 2:
            return Response(
                {"detail": "Both events must be in this space."}, status=404
            )
        notes = list(
            Note.objects.filter(space=space, pk__in=values["source_note_ids"])
        )
        if len(notes) != len(set(values["source_note_ids"])):
            return Response(
                {"detail": "Source notes must be in this space."}, status=404
            )
        try:
            relation = upsert_event_relation(
                actor=request.user,
                space=space,
                left_event=events[0],
                right_event=events[1],
                relation_kind=values["relation_kind"],
                decision=values["decision"],
                reason=values.get("reason", ""),
                source_note_ids=values["source_note_ids"],
            )
        except ChatAnalysisPermissionError as error:
            return Response({"detail": str(error)}, status=403)
        except (ChatAnalysisConflict, ChatAnalysisError) as error:
            return Response({"detail": str(error)}, status=409)
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.event_relation_updated",
            resource_type="event_relation",
            resource_id=relation.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response(
            {"data": EventRelationSerializer(relation).data}, status=201
        )
