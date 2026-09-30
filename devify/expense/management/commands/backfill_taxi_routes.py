"""Fill missing taxi routes from already attached itineraries."""

import os

from django.core.management.base import BaseCommand

from expense.constants import ExpenseCategory
from expense.models import Invoice
from expense.services.decoder import DecodeError, decode_source
from expense.services.taxi_route import merge_route, parse_amap_itinerary


class Command(BaseCommand):
    help = "Fill taxi invoice routes from their linked itinerary PDFs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the changes. Without it, only report them.",
        )

    def handle(self, *args, **options):
        changed = {}
        copies = (
            Invoice.objects.filter(
                status=Invoice.Status.DUPLICATE,
                duplicate_of__category=ExpenseCategory.TRANSPORT_LOCAL,
            )
            .select_related("duplicate_of", "email_attachment", "source_file")
            .order_by("id")
        )
        for copy in copies.iterator():
            primary = changed.get(copy.duplicate_of_id) or copy.duplicate_of
            route = (
                copy.ticket_details
                if isinstance(copy.ticket_details, dict)
                else {}
            )
            if not route.get("from_address") or not route.get("to_address"):
                source = copy.email_attachment or copy.source_file
                path = getattr(source, "file_path", "")
                filename = getattr(source, "filename", "")
                if (
                    path
                    and os.path.isfile(path)
                    and filename.lower().endswith(".pdf")
                    and "行程单" in filename
                ):
                    try:
                        route = merge_route(
                            route,
                            parse_amap_itinerary(
                                decode_source(path, "application/pdf").text
                            ),
                        )
                    except DecodeError:
                        continue
            merged = merge_route(primary.ticket_details, route)
            if merged != primary.ticket_details:
                primary.ticket_details = merged
                changed[primary.id] = primary

        self.stdout.write(f"{len(changed)} invoice(s) would change")
        if not options["apply"]:
            self.stdout.write("Not written; pass --apply to write.")
            return
        for invoice in changed.values():
            invoice.save(update_fields=["ticket_details", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"Updated {len(changed)}"))
