"""Regression coverage for todo source conversation links."""

from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from threadline.models import EmailMessage, EmailTodo
from threadline.serializers.email_todo import EmailTodoListSerializer


class TestTodoSourceConversation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username=f"source-{uuid4().hex}")
        cls.email = EmailMessage.objects.create(
            user=cls.user,
            message_id=uuid4().hex,
            subject="Synthetic source email",
            sender="qa@example.invalid",
            recipients="qa@example.invalid",
            received_at=timezone.now(),
        )

    def test_list_contains_source_email_uuid(self):
        todo = EmailTodo.objects.create(
            user=self.user, email_message=self.email, content="Test todo"
        )
        email = EmailTodoListSerializer(todo).data["email_message"]
        self.assertEqual(email["uuid"], str(self.email.uuid))
        self.assertEqual(email["id"], self.email.id)

    def test_manual_todo_has_no_source_email(self):
        todo = EmailTodo.objects.create(user=self.user, content="Manual todo")
        self.assertIsNone(EmailTodoListSerializer(todo).data["email_message"])
