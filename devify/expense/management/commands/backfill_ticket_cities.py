"""Re-derive the city of existing train tickets from their station."""

from django.core.management.base import BaseCommand

from expense.models import Invoice
from expense.services.extractor import resolve_city


class Command(BaseCommand):
    help = (
        "Look up the city of stored train tickets from their to_station, "
        "the way recognition does now."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the changes. Without it, only report them.",
        )

    def handle(self, *args, **options):
        changed = []
        for invoice in Invoice.objects.exclude(ticket_details={}).iterator():
            details = invoice.ticket_details or {}
            if not details.get("to_station"):
                continue
            city = resolve_city(details, invoice.city)
            if city and city != invoice.city:
                changed.append((invoice, city))

        for invoice, city in changed:
            self.stdout.write(
                f"  {invoice.id}  {invoice.ticket_details.get('to_station')}"
                f"  {invoice.city or '(empty)'} -> {city}"
            )
        self.stdout.write(f"{len(changed)} ticket(s) would change")

        if not options["apply"]:
            self.stdout.write("Not written; pass --apply to write.")
            return

        for invoice, city in changed:
            invoice.city = city
            invoice.save(update_fields=["city"])
        self.stdout.write(self.style.SUCCESS(f"Updated {len(changed)}"))
