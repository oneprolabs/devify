"""
Unit tests for EmailTaskMonitor

These exist because the module read settings.TASK_TIMEOUT_MINUTES without
importing settings, and every method here catches Exception and returns
{'error': ...} instead of raising. The NameError therefore never reached a
caller: it became one log line, get_task_status_summary returned a payload
with no health_status, and simple_health — the endpoint documented for load
balancers — read the missing key as 'unknown' and answered 503 forever.

So the assertion that matters in each test is 'error' not in result. A test
that only checks the happy-path keys would pass on the degraded payload too.
"""

from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from threadline.models import EmailTask
from threadline.utils.monitoring import (
    EmailTaskMonitor,
    get_task_status_summary,
)


class EmailTaskMonitorTest(TestCase):
    """Both metric paths must compute, not degrade into an error payload."""

    def setUp(self):
        # The module-level accessors cache for 60s and TestCase rolls back
        # the database but not the cache, so a stale summary would otherwise
        # leak between tests here.
        cache.clear()
        now = timezone.now()
        EmailTask.objects.create(
            task_type='IMAP_EMAIL_FETCH',
            status=EmailTask.TaskStatus.COMPLETED,
            started_at=now - timedelta(minutes=5),
            completed_at=now - timedelta(minutes=4),
        )
        EmailTask.objects.create(
            task_type='IMAP_EMAIL_FETCH',
            status=EmailTask.TaskStatus.FAILED,
        )
        # Started long enough ago to land in the timeout branch, which is the
        # code that reads TASK_TIMEOUT_MINUTES.
        EmailTask.objects.create(
            task_type='IMAP_EMAIL_FETCH',
            status=EmailTask.TaskStatus.RUNNING,
            started_at=now - timedelta(hours=6),
        )

    def test_get_task_metrics_computes(self):
        metrics = EmailTaskMonitor.get_task_metrics()

        self.assertNotIn('error', metrics, metrics.get('error'))
        self.assertEqual(metrics['basic_counts']['total_tasks'], 3)
        self.assertEqual(metrics['basic_counts']['completed_tasks'], 1)
        self.assertEqual(metrics['basic_counts']['failed_tasks'], 1)
        # Reached only if the timeout threshold was computed.
        self.assertEqual(metrics['health_indicators']['timeout_tasks'], 1)

    def test_get_task_status_summary_computes(self):
        summary = get_task_status_summary()

        self.assertNotIn('error', summary, summary.get('error'))
        self.assertIn('health_status', summary)
        self.assertEqual(summary['timeout_tasks_count'], 1)
        # One running task over the threshold: warning, not healthy.
        self.assertEqual(summary['health_status'], 'warning')

    def test_status_summary_is_healthy_with_nothing_overdue(self):
        EmailTask.objects.filter(
            status=EmailTask.TaskStatus.RUNNING
        ).update(started_at=timezone.now())

        summary = get_task_status_summary()

        self.assertNotIn('error', summary, summary.get('error'))
        self.assertEqual(summary['timeout_tasks_count'], 0)
        self.assertEqual(summary['health_status'], 'healthy')


class SimpleHealthEndpointTest(TestCase):
    """The load-balancer endpoint must answer 200 when nothing is overdue."""

    def setUp(self):
        cache.clear()

    def test_simple_health_returns_200_when_healthy(self):
        response = self.client.get(reverse('simple_health'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'healthy')

    def test_simple_health_returns_503_when_a_task_is_overdue(self):
        EmailTask.objects.create(
            task_type='IMAP_EMAIL_FETCH',
            status=EmailTask.TaskStatus.RUNNING,
            started_at=timezone.now() - timedelta(hours=6),
        )

        response = self.client.get(reverse('simple_health'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'warning')
