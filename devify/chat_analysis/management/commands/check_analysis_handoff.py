"""Check whether the previous analysis consumer can safely resume jobs."""

from django.core.management.base import BaseCommand, CommandError

from chat_analysis.models import AnalysisJob


class Command(BaseCommand):
    help = "Refuse rollback while jobs require the current analysis consumer."

    def handle(self, *args, **options):
        active = AnalysisJob.objects.filter(
            state__in=(AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING),
        )
        if active.filter(state=AnalysisJob.State.RUNNING).exists():
            raise CommandError("Running analysis jobs must finish first.")
        if active.filter(specification__snapshot_pending=True).exists():
            raise CommandError(
                "Queued deferred input must be frozen before rollback."
            )
        self.stdout.write("Analysis jobs are compatible with rollback.")
