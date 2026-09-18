"""
The city on a train ticket is looked up, not judged.

Recognition used to ask the model for `city` alongside the station names,
which is a second reading of something the document already states — on the
one field trip grouping runs on. Production shows what that costs: the same
ticket read three times gave 北京 twice and 上海 once, and the spelling
varied between 北京 and 北京市, which downstream counts as two places.
"""

import pytest

from expense.services.extractor import (_STATION_CITY_PATH, _station_cities,
                                        resolve_city)


class TestStationList:
    def test_the_file_is_where_the_code_looks(self):
        """
        An unanchored `data` line in .gitignore swallowed this directory
        once already and the code shipped without the file it reads — which
        fails silently, since a missing list just falls back to the model.
        Checking the path exists catches a file that never got committed.
        """
        assert _STATION_CITY_PATH.is_file(), (
            f"{_STATION_CITY_PATH} is missing — check it is not gitignored"
        )

    def test_the_list_is_loaded(self):
        stations = _station_cities()

        assert len(stations) > 3000
        assert stations["北京南"] == "北京"
        assert stations["上海虹桥"] == "上海"

    def test_every_station_names_a_city(self):
        assert all(name and city for name, city in _station_cities().items())

    def test_no_city_is_mangled_by_the_canonical_form(self):
        """
        Suggestion names come from these values through canonical_city, so
        a value it truncates becomes a group named after a non-place.
        """
        from expense.services.trips import canonical_city

        mangled = sorted(
            c for c in set(_station_cities().values())
            if canonical_city(c) != c and not c.endswith("市")
        )

        assert mangled == []

    def test_cities_are_spelled_without_a_suffix(self):
        """
        The list is also what makes the spelling consistent, so a value out
        of it must not carry 市 — otherwise it reintroduces the split that
        sent a Beijing-based user's home city to Shanghai.
        """
        suffixed = [c for c in set(_station_cities().values())
                    if c.endswith("市")]

        assert suffixed == []


class TestResolveCity:
    def test_the_station_wins_over_the_model(self):
        """The production failure: the model said 上海 for a ticket into
        北京南, and city is what trip grouping reads."""
        assert resolve_city({"to_station": "北京南"}, "上海") == "北京"

    def test_the_station_answers_when_the_model_did_not(self):
        assert resolve_city({"to_station": "上海虹桥"}, "") == "上海"

    def test_surrounding_space_does_not_break_the_lookup(self):
        assert resolve_city({"to_station": "  杭州东  "}, "") == "杭州"

    @pytest.mark.parametrize(
        "station,expected",
        [("北京南站", "北京"), ("上海虹桥站", "上海"), ("  杭州东站 ", "杭州")],
    )
    def test_a_trailing_station_character_still_matches(
        self, station, expected
    ):
        """
        Not one of the 3384 entries ends in 站, but tickets print it and
        models read it back. A miss here leaves the city empty, and an
        empty city on a long-haul ticket neither opens nor closes a trip.
        """
        assert resolve_city({"to_station": station}, "") == expected

    def test_a_bare_station_character_is_not_stripped_to_nothing(self):
        assert resolve_city({"to_station": "站"}, "上海") == "上海"

    @pytest.mark.parametrize(
        "ticket_details",
        [None, {}, {"to_station": ""}, {"to_station": "不存在的站"},
         {"from_station": "北京南"}, "not a dict"],
    )
    def test_the_model_answers_for_everything_else(self, ticket_details):
        """Taxis, hotels, meals, and any station not in the list."""
        assert resolve_city(ticket_details, "深圳市") == "深圳市"

    def test_nothing_in_means_nothing_out(self):
        assert resolve_city({}, "") == ""
        assert resolve_city({}, None) == ""
