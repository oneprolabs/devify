# Reference data

## `railway_station_city.json`

Station name → city, for the whole Chinese railway network. Parsed from
12306's own station list, which the site publishes for its booking form:

    https://kyfw.12306.cn/otn/resources/js/framework/station_name.js

Each `@`-separated record is pipe-delimited; field 1 is the station name
and field 7 is the city it belongs to.

To refresh it:

    python manage.py refresh_station_cities

This exists so that a train ticket's city is looked up rather than judged.
Recognition used to ask the model for `city` alongside the station names,
which is one more field to get wrong on a document that already states the
answer — and `city` is what trip grouping runs on.
