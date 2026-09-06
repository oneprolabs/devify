"""
Integration tests for the threadline list query filters.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from ..fixtures.factories import EmailMessageFactory


@pytest.mark.django_db
@pytest.mark.integration
class TestThreadlineReceivedAfterFilter:
    """
    The list's time-range control sends the start of its window.
    """

    def _titles(self, response):
        return {item['subject'] for item in response.data['data']['list']}

    def test_keeps_only_threadlines_at_or_after_the_moment(
        self, authenticated_api_client, test_user
    ):
        now = timezone.now()
        EmailMessageFactory(
            user=test_user,
            subject='recent',
            received_at=now - timedelta(days=3),
        )
        EmailMessageFactory(
            user=test_user,
            subject='old',
            received_at=now - timedelta(days=60),
        )

        url = reverse('threadlines-list')
        cutoff = (now - timedelta(days=30)).isoformat()
        response = authenticated_api_client.get(
            url, {'received_after': cutoff}
        )

        assert response.status_code == status.HTTP_200_OK
        assert self._titles(response) == {'recent'}

    def test_a_bare_date_starts_at_midnight(
        self, authenticated_api_client, test_user
    ):
        tz = timezone.get_current_timezone()
        day = timezone.localtime(timezone.now(), tz).date()
        start_of_day = timezone.make_aware(
            timezone.datetime.combine(day, timezone.datetime.min.time()), tz
        )
        EmailMessageFactory(
            user=test_user,
            subject='this morning',
            received_at=start_of_day + timedelta(minutes=1),
        )
        EmailMessageFactory(
            user=test_user,
            subject='last night',
            received_at=start_of_day - timedelta(minutes=1),
        )

        url = reverse('threadlines-list')
        response = authenticated_api_client.get(
            url, {'received_after': day.isoformat()}
        )

        assert response.status_code == status.HTTP_200_OK
        assert self._titles(response) == {'this morning'}

    def test_an_unparseable_value_is_rejected(
        self, authenticated_api_client, test_user
    ):
        EmailMessageFactory(user=test_user, subject='kept')

        url = reverse('threadlines-list')
        response = authenticated_api_client.get(
            url, {'received_after': 'last-thursday'}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_no_filter_returns_everything(
        self, authenticated_api_client, test_user
    ):
        now = timezone.now()
        EmailMessageFactory(
            user=test_user, subject='recent', received_at=now
        )
        EmailMessageFactory(
            user=test_user,
            subject='old',
            received_at=now - timedelta(days=400),
        )

        url = reverse('threadlines-list')
        response = authenticated_api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert self._titles(response) == {'recent', 'old'}


@pytest.mark.django_db
@pytest.mark.integration
class TestThreadlineStats:
    """
    The header strip counts the whole list, not the page on screen.
    """

    def test_counts_cover_every_page(
        self, authenticated_api_client, test_user
    ):
        now = timezone.now()
        for _ in range(3):
            EmailMessageFactory(
                user=test_user, status='success', received_at=now
            )
        EmailMessageFactory(user=test_user, status='fetched', received_at=now)
        EmailMessageFactory(
            user=test_user,
            status='success',
            received_at=now - timedelta(days=30),
        )

        response = authenticated_api_client.get(reverse('threadlines-stats'))

        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['total'] == 5
        assert data['this_week'] == 4
        assert data['pending'] == 1
        assert data['completed'] == 4

    def test_another_users_threadlines_are_not_counted(
        self, authenticated_api_client, test_user
    ):
        EmailMessageFactory(user=test_user, status='success')
        EmailMessageFactory(status='success')

        response = authenticated_api_client.get(reverse('threadlines-stats'))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['total'] == 1
