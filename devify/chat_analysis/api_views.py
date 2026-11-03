import uuid

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_analysis.api_serializers import (
    EventCreateSerializer,
    EventEvidenceSerializer,
    EventNoteSerializer,
    EventRelationCreateSerializer,
    EventRelationSerializer,
    EventSerializer,
    EventTagAssignmentCreateSerializer,
    EventTagAssignmentSerializer,
    EventTagCreateSerializer,
    EventTagSerializer,
    EventUpdateSerializer,
    EvidenceCreateSerializer,
    NoteCreateSerializer,
    NoteEvidenceSerializer,
    NoteSerializer,
    NoteUpdateSerializer,
    QuestionAnswerSerializer,
    QuestionCreateSerializer,
    ReportSerializer,
    TopicSubscriptionCreateSerializer,
    TopicSubscriptionSerializer,
)
from chat_analysis.models import (
    Event,
    EventNote,
    EventRelation,
    EventTag,
    EventTagAssignment,
    Note,
    NoteEvidence,
    QuestionAnswer,
    Report,
    TopicSubscription,
)
from chat_analysis.question_tasks import dispatch_question_answer
from chat_analysis.report_services import create_report_snapshot
from chat_analysis.report_tasks import dispatch_report_generation
from chat_analysis.services import (
    ChatAnalysisConflict,
    ChatAnalysisError,
    ChatAnalysisPermissionError,
    add_note_evidence,
    assign_note_events,
    create_event,
    create_note,
    delete_event,
    delete_note,
    upsert_event_relation,
)
from chat_analysis.topic_services import answer_question
from chat_domain.models import Message, MessagePart
from spaces.models import Space, SpaceMembership, SpaceTakeover
from spaces.services import (
    SpacePermissionService,
    audit_space_action,
    check_daily_ai_quota,
)


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
    def get_detail(self, request, space_id, question_id):
        space, _ = self._space(request, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        question = get_object_or_404(QuestionAnswer, pk=question_id, space=space, created_by=request.user)
        return Response({"data": QuestionAnswerSerializer(question).data})

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
            note.evidence.select_related("message__conversation"), many=True
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
        events = Event.objects.filter(space=space).prefetch_related("tag_assignments__tag").order_by(
            "-last_activity_at", "-id"
        )
        state = request.query_params.get("status")
        if state:
            events = events.filter(status=state)
        tag_key = request.query_params.get("tag_key", "").strip()
        if tag_key:
            events = events.filter(tag_assignments__tag__tag_key=tag_key).distinct()
        conversation_id = request.query_params.get(
            "conversation_id", ""
        ).strip()
        if conversation_id:
            if not conversation_id.isdigit():
                return Response(
                    {"detail": "conversation_id must be an integer."},
                    status=400,
                )
            events = events.filter(
                note_links__note__evidence__message__conversation_id=int(
                    conversation_id
                )
            ).distinct()
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
        event = Event.objects.prefetch_related("tag_assignments__tag").get(pk=event.pk)
        data = EventSerializer(event).data
        data["note_ids"] = list(
            event.note_links.order_by("id").values_list("note_id", flat=True)
        )
        data["evidence"] = EventEvidenceSerializer(
            event.evidence.select_related("message")
            .order_by("message__occurred_at", "id")[:200],
            many=True,
        ).data
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

    def get(self, request, event_id):
        event = get_object_or_404(Event.objects.select_related("space"), pk=event_id)
        space, _ = _authorized_space(request.user, event.space_id)
        if space is None:
            return Response({"detail": "Event not found."}, status=404)
        paginator = AnalysisPagination()
        notes = Note.objects.filter(
            space=space, event_links__event=event
        ).distinct().order_by("-start_at", "-id")
        page = paginator.paginate_queryset(notes, request, view=self)
        page = list(page)
        data = NoteSerializer(page, many=True).data
        evidence_by_note = {}
        evidence = NoteEvidence.objects.filter(
            note_id__in=[note.pk for note in page]
        ).select_related("message__conversation")
        for item in NoteEvidenceSerializer(evidence, many=True).data:
            evidence_by_note.setdefault(item["note_id"], []).append(item)
        for item in data:
            item["evidence"] = evidence_by_note.get(item["id"], [])
        return Response({"data": {"list": data, "pagination": _pagination_data(paginator)}})

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


class EventRelationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, relation_id, *, write=False):
        relation = get_object_or_404(EventRelation.objects.select_related("space", "left_event", "right_event"), pk=relation_id)
        space, _ = _authorized_space(request.user, relation.space_id, write=write)
        return relation if space else None

    def get(self, request, relation_id):
        relation = self._get(request, relation_id)
        if relation is None:
            return Response({"detail": "Relation not found."}, status=404)
        return Response({"data": EventRelationSerializer(relation).data})

    @transaction.atomic
    def patch(self, request, relation_id):
        relation = self._get(request, relation_id, write=True)
        if relation is None:
            return Response({"detail": "Relation not found."}, status=404)
        serializer = EventRelationCreateSerializer(data={
            "left_event_id": relation.left_event_id,
            "right_event_id": relation.right_event_id,
            "relation_kind": request.data.get("relation_kind", relation.relation_kind),
            "decision": request.data.get("decision", relation.decision),
            "reason": request.data.get("reason", relation.reason),
            "source_note_ids": request.data.get("source_note_ids", relation.source_note_ids),
        })
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        notes = list(Note.objects.filter(space=relation.space, pk__in=values["source_note_ids"]))
        if len(notes) != len(set(values["source_note_ids"])):
            return Response({"detail": "Source notes must be in this space."}, status=404)
        try:
            relation = upsert_event_relation(actor=request.user, space=relation.space, left_event=relation.left_event, right_event=relation.right_event, relation_kind=values["relation_kind"], decision=values["decision"], reason=values.get("reason", ""), source_note_ids=values["source_note_ids"])
        except (ChatAnalysisPermissionError, ChatAnalysisConflict, ChatAnalysisError) as error:
            return Response({"detail": str(error)}, status=403 if isinstance(error, ChatAnalysisPermissionError) else 409)
        return Response({"data": EventRelationSerializer(relation).data})

    @transaction.atomic
    def delete(self, request, relation_id):
        relation = self._get(request, relation_id, write=True)
        if relation is None:
            return Response({"detail": "Relation not found."}, status=404)
        relation.delete()
        return Response(status=204)


class SpaceTopicSubscriptionListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, _ = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        subscriptions = TopicSubscription.objects.filter(space=space, created_by=request.user)
        return Response({"data": TopicSubscriptionSerializer(subscriptions, many=True).data})

    def post(self, request, space_id):
        space, _ = _authorized_space(request.user, space_id, write=True)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        serializer = TopicSubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = TopicSubscription.objects.create(space=space, created_by=request.user, **serializer.validated_data)
        return Response({"data": TopicSubscriptionSerializer(subscription).data}, status=201)


class TopicSubscriptionDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, topic_id, *, write=False):
        topic = get_object_or_404(TopicSubscription.objects.select_related("space"), pk=topic_id, created_by=request.user)
        space, _ = _authorized_space(request.user, topic.space_id, write=write)
        return topic if space else None

    def get(self, request, topic_id):
        topic = self._get(request, topic_id)
        if topic is None:
            return Response({"detail": "Topic not found."}, status=404)
        return Response({"data": TopicSubscriptionSerializer(topic).data})

    def patch(self, request, topic_id):
        topic = self._get(request, topic_id, write=True)
        if topic is None:
            return Response({"detail": "Topic not found."}, status=404)
        serializer = TopicSubscriptionCreateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(topic, field, value)
        topic.save(update_fields=tuple(serializer.validated_data) + ("updated_at",))
        return Response({"data": TopicSubscriptionSerializer(topic).data})

    def delete(self, request, topic_id):
        topic = self._get(request, topic_id, write=True)
        if topic is None:
            return Response({"detail": "Topic not found."}, status=404)
        topic.delete()
        return Response(status=204)


class TopicRunAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, topic_id):
        topic = get_object_or_404(TopicSubscription.objects.select_related("space"), pk=topic_id, created_by=request.user)
        space, _ = _authorized_space(request.user, topic.space_id)
        if space is None:
            return Response({"detail": "Topic not found."}, status=404)
        reports = Report.objects.filter(space=space, created_by=request.user, source_info__subscription_id=topic.pk).order_by("-created_at", "-id")[:50]
        return Response({"data": ReportSerializer(reports, many=True).data})

    @transaction.atomic
    def post(self, request, topic_id):
        topic = get_object_or_404(TopicSubscription.objects.select_related("space"), pk=topic_id, created_by=request.user)
        space, takeover = _authorized_space(request.user, topic.space_id, write=True)
        if space is None:
            return Response({"detail": "Topic not found."}, status=404)
        request_key = f"topic-{topic.pk}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
        try:
            report, created = create_report_snapshot(actor=request.user, space=space, request_key=request_key, title=topic.title, filters=topic.filters, include_open=topic.include_open)
        except (ChatAnalysisPermissionError, ChatAnalysisConflict) as error:
            return Response({"detail": str(error)}, status=403 if isinstance(error, ChatAnalysisPermissionError) else 409)
        if created:
            report.source_info = {**(report.source_info or {}), "kind": "topic_subscription", "subscription_id": topic.pk}
            report.status = Report.Status.QUEUED
            report.processing = {**(report.processing or {}), "generator": "llm_pending", "version": "report.llm.v1"}
            report.save(update_fields=("source_info", "status", "processing", "updated_at"))
            transaction.on_commit(lambda: dispatch_report_generation(report))
        return Response({"data": ReportSerializer(report).data}, status=202 if created else 200)


class SpaceQuestionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _space(self, request, space_id):
        return _authorized_space(request.user, space_id)

    def get(self, request, space_id):
        space, _ = self._space(request, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        questions = QuestionAnswer.objects.filter(space=space, created_by=request.user)[:50]
        return Response({"data": QuestionAnswerSerializer(questions, many=True).data})

    def post(self, request, space_id):
        space, takeover = self._space(request, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        quota_error = check_daily_ai_quota(space)
        if quota_error:
            return Response({"detail": quota_error}, status=429)
        serializer = QuestionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = QuestionAnswer.objects.create(space=space, created_by=request.user, question=serializer.validated_data["question"], scope={key: serializer.validated_data[key] for key in ("event_ids", "note_ids", "conversation_ids", "tag_keys", "keywords") if serializer.validated_data.get(key)})
        transaction.on_commit(lambda: dispatch_question_answer(question))
        if takeover:
            audit_space_action(actor=request.user, space=space, action="chat.question_queued", resource_type="question", resource_id=question.pk, metadata={"takeover_id": takeover.pk})
        return Response({"data": QuestionAnswerSerializer(question).data}, status=202)


class SpaceEventTagListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, _ = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        tags = EventTag.objects.filter(space=space)
        return Response({"data": EventTagSerializer(tags, many=True).data})

    def post(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id, write=True)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        serializer = EventTagCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tag = EventTag.objects.create(space=space, created_by=request.user, **serializer.validated_data)
        except IntegrityError:
            return Response({"detail": "This tag already exists."}, status=409)
        audit_space_action(actor=request.user, space=space, action="chat.event_tag_created", resource_type="event_tag", resource_id=tag.pk, metadata={"takeover_id": takeover.pk if takeover else None})
        return Response({"data": EventTagSerializer(tag).data}, status=201)


class EventTagDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, tag_id, *, write=False):
        tag = get_object_or_404(EventTag.objects.select_related("space"), pk=tag_id)
        space, _ = _authorized_space(request.user, tag.space_id, write=write)
        return tag if space else None

    def get(self, request, tag_id):
        tag = self._get(request, tag_id)
        return Response({"data": EventTagSerializer(tag).data}) if tag else Response({"detail": "Tag not found."}, status=404)

    def patch(self, request, tag_id):
        tag = self._get(request, tag_id, write=True)
        if tag is None:
            return Response({"detail": "Tag not found."}, status=404)
        serializer = EventTagCreateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(tag, field, value)
        try:
            tag.save(update_fields=tuple(serializer.validated_data) + ("updated_at",))
        except IntegrityError:
            return Response({"detail": "This tag already exists."}, status=409)
        return Response({"data": EventTagSerializer(tag).data})

    def delete(self, request, tag_id):
        tag = self._get(request, tag_id, write=True)
        if tag is None:
            return Response({"detail": "Tag not found."}, status=404)
        tag.delete()
        return Response(status=204)


class EventTagAssignmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        event = get_object_or_404(Event.objects.select_related("space"), pk=event_id)
        space, _ = _authorized_space(request.user, event.space_id, write=True)
        if space is None:
            return Response({"detail": "Event not found."}, status=404)
        if not _editable(request.user, event):
            return Response({"detail": "Event edit permission required."}, status=403)
        serializer = EventTagAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tag = EventTag.objects.filter(space=space, pk=serializer.validated_data["tag_id"]).first()
        if tag is None:
            return Response({"detail": "Tag not found."}, status=404)
        assignment, _ = EventTagAssignment.objects.get_or_create(event=event, tag=tag, defaults={"created_by": request.user})
        return Response({"data": EventTagAssignmentSerializer(assignment).data}, status=201)

    def delete(self, request, event_id, tag_id):
        event = get_object_or_404(Event.objects.select_related("space"), pk=event_id)
        space, _ = _authorized_space(request.user, event.space_id, write=True)
        if space is None or not _editable(request.user, event):
            return Response({"detail": "Event not found."}, status=404)
        assignment = EventTagAssignment.objects.filter(event=event, tag_id=tag_id).first()
        if assignment is None:
            return Response({"detail": "Tag assignment not found."}, status=404)
        assignment.delete()
        return Response(status=204)


class QuestionAnswerDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id, question_id):
        space, _ = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        question = get_object_or_404(QuestionAnswer, pk=question_id, space=space, created_by=request.user)
        return Response({"data": QuestionAnswerSerializer(question).data})


class SpaceResourceCopyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, space_id):
        target = get_object_or_404(Space, pk=space_id)
        source_id = request.data.get("source_space_id")
        resource_type = request.data.get("resource_type")
        resource_ids = request.data.get("resource_ids", [])
        copy_notes = bool(request.data.get("copy_notes", False))
        if not isinstance(resource_ids, list) or not resource_ids or resource_type not in ("note", "event"):
            return Response({"detail": "resource_type and non-empty resource_ids are required."}, status=400)
        source = get_object_or_404(Space, pk=source_id)
        if not SpacePermissionService.can_read(request.user, source):
            return Response({"detail": "Source space not found."}, status=404)
        if not SpacePermissionService.can_upload(request.user, target):
            return Response({"detail": "Target space is not writable."}, status=403)
        copied = []
        warnings = []
        if resource_type == "note":
            for note in Note.objects.filter(space=source, pk__in=resource_ids):
                copied_note = Note.objects.create(space=target, created_by=request.user, note_key=f"copy-{source.pk}-{note.pk}-{uuid.uuid4().hex[:12]}", title=note.title, content=note.content, structured_data=note.structured_data, generation_version=note.generation_version, start_at=note.start_at, end_at=note.end_at, origin=Note.Origin.MANUAL, assignment_mode=Note.AssignmentMode.MANUAL)
                copied.append({"source_id": note.pk, "id": copied_note.pk, "type": "note"})
                warnings.append({"source_id": note.pk, "code": "evidence_not_copied", "detail": "原始消息证据仍属于源空间，未跨空间复制。"})
        else:
            for event in Event.objects.filter(space=source, pk__in=resource_ids):
                copied_event = Event.objects.create(space=target, created_by=request.user, event_key=f"copy-{source.pk}-{event.pk}-{uuid.uuid4().hex[:12]}", title=event.title, content=event.content, status=event.status, opened_at=event.opened_at, last_activity_at=event.last_activity_at)
                copied.append({"source_id": event.pk, "id": copied_event.pk, "type": "event"})
                source_notes = list(Note.objects.filter(space=source, event_links__event=event).distinct())
                if copy_notes:
                    copied_note_ids = []
                    for note in source_notes:
                        copied_note = Note.objects.create(space=target, created_by=request.user, note_key=f"copy-{source.pk}-{note.pk}-{uuid.uuid4().hex[:12]}", title=note.title, content=note.content, structured_data=note.structured_data, generation_version=note.generation_version, start_at=note.start_at, end_at=note.end_at, origin=Note.Origin.MANUAL, assignment_mode=Note.AssignmentMode.MANUAL)
                        EventNote.objects.create(event=copied_event, note=copied_note, created_by=request.user)
                        copied_note_ids.append(copied_note.pk)
                        warnings.append({"source_id": note.pk, "code": "evidence_not_copied", "detail": "整理记录已复制，但原始消息证据仍属于源空间。"})
                    copied[-1]["copied_note_ids"] = copied_note_ids
                elif source_notes:
                    warnings.append({"source_id": event.pk, "code": "notes_not_copied", "detail": "事件关联整理记录未复制；请求 copy_notes=true 可复制独立整理记录。"})
        audit_space_action(actor=request.user, space=target, action="space.resource_copied", resource_type=resource_type, metadata={"source_space_id": source.pk, "copied": copied, "warnings": warnings})
        return Response({"data": {"source_space_id": source.pk, "target_space_id": target.pk, "copied": copied, "warnings": warnings}}, status=201)
