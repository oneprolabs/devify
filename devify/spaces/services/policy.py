"""Global space creation policy lookup."""

from spaces.models import SpacePolicy


def get_space_policy():
    policy, _ = SpacePolicy.objects.get_or_create(singleton_key="default")
    return policy
