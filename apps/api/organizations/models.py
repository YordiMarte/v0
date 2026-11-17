import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class OrganizationQuerySet(models.QuerySet):
    def for_user(self, user):
        """Only the organizations the user belongs to.

        This is the single place where tenant isolation starts: every view
        that exposes organization data must build its queryset from here.
        """
        return self.filter(memberships__user=user)


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=70, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrganizationQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:50] or "org"
            self.slug = f"{base}-{secrets.token_hex(3)}"
        super().save(*args, **kwargs)


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "organization"], name="unique_membership")
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"
