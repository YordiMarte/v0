from django.db import transaction

from accounts.models import User
from organizations.models import Membership, Organization


@transaction.atomic
def register_owner(
    *, email: str, password: str, full_name: str, organization_name: str
) -> tuple[User, Organization]:
    """Create a user, their organization and the owner membership atomically.

    If any step fails nothing is saved, so we never end up with a user who
    belongs to no organization.
    """
    user = User.objects.create_user(email=email, password=password, full_name=full_name)
    organization = Organization.objects.create(name=organization_name)
    Membership.objects.create(user=user, organization=organization, role=Membership.Role.OWNER)
    return user, organization
