"""Refresh the station-to-city list from 12306."""

import json
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError

SOURCE_URL = (
    "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
)
DEST = (
    Path(__file__).resolve().parents[2] / "data" / "railway_station_city.json"
)

# Field positions in each pipe-delimited record.
NAME_FIELD = 1
CITY_FIELD = 7


class Command(BaseCommand):
    help = "Refresh expense/data/railway_station_city.json from 12306."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing the file.",
        )

    def handle(self, *args, **options):
        try:
            response = requests.get(SOURCE_URL, timeout=30)
            response.raise_for_status()
            # requests guesses ISO-8859-1 for a text/* response with no
            # charset, which turns every station name into mojibake that
            # still parses — non-empty names, no error, a silently ruined
            # reference file.
            response.encoding = "utf-8"
        except requests.RequestException as exc:
            raise CommandError(
                f"Could not fetch the station list.\n"
                f"  Likely cause: 12306 is unreachable from this host, or it "
                f"moved the file.\n"
                f"  Try: open {SOURCE_URL} in a browser to check, "
                f"then rerun.\n"
                f"  Detail: {exc}"
            ) from exc

        try:
            body = response.text.split("'")[1]
        except IndexError:
            raise CommandError(
                "The station list did not look like the expected JS.\n"
                "  Likely cause: 12306 changed the format of the file.\n"
                f"  Try: read {SOURCE_URL} and update this command to match."
            )

        stations = {}
        for record in body.split("@"):
            fields = record.split("|")
            if len(fields) <= CITY_FIELD:
                continue
            name = fields[NAME_FIELD].strip()
            city = fields[CITY_FIELD].strip()
            if name and city:
                stations[name] = city

        if not stations:
            raise CommandError(
                "Parsed the station list and found no stations.\n"
                "  Likely cause: the record layout changed.\n"
                f"  Try: read {SOURCE_URL} and update the field positions."
            )

        current = {}
        if DEST.exists():
            current = json.loads(DEST.read_text(encoding="utf-8"))

        added = sorted(set(stations) - set(current))
        removed = sorted(set(current) - set(stations))
        moved = sorted(
            n for n in set(stations) & set(current)
            if stations[n] != current[n]
        )

        self.stdout.write(f"{len(stations)} stations, {len(added)} new, "
                          f"{len(removed)} gone, {len(moved)} moved city")
        for name in moved:
            self.stdout.write(
                f"  {name}: {current[name]} -> {stations[name]}"
            )

        # A partial upstream change can still yield parseable records, so
        # size is the check that a good file is not overwritten by a bad
        # one. Losing a tenth of the network at once is not a real edit.
        if current and len(removed) > len(current) // 10:
            raise CommandError(
                f"Refusing to write: {len(removed)} of {len(current)} "
                f"stations disappeared.\n"
                f"  Likely cause: 12306 changed the format and only part "
                f"of the file parsed.\n"
                f"  Try: read {SOURCE_URL} and check the field positions "
                f"in this command."
            )

        if options["dry_run"]:
            self.stdout.write("Dry run; nothing written.")
            return

        DEST.write_text(
            json.dumps(stations, ensure_ascii=False, indent=0, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(f"Wrote {DEST}"))
