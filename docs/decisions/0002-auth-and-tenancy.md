# 0002. Authentication and multi-tenancy

## Context

Users belong to one or more companies. Documents and conversations (added in
later days) must never be visible across companies, and the API must resist
credential guessing.

## Decisions

1. **Custom user model with email as the login**, created before the first
   migration. Changing the user model after migrating is very painful in
   Django. Emails are stored lowercase and checked case-insensitively.
2. **Organization and Membership with a role** (owner, admin, member), instead
   of a single foreign key on the user. A user can belong to several
   organizations, and permissions can differ per organization.
3. **UUID primary keys for organizations**, so URLs cannot be enumerated.
4. **Tenant scoping in one place**: `Organization.objects.for_user(user)`.
   Resources outside the user's organizations answer 404, not 403, so their
   existence is not revealed. Isolation is covered by dedicated tests.
5. **JWT with short-lived access tokens (15 min) and refresh tokens (7 days)**
   through SimpleJWT. A stolen access token is useful only briefly, and users
   are not forced to log in every 15 minutes.
6. **Throttling of 10 requests per minute** on register and login, to slow
   down brute force and credential stuffing.
7. **Registration is a single transaction** that creates the user, the
   organization and the owner membership, or nothing.

## Consequences and limits

- Refresh tokens are not revocable yet. Logging out only discards them on the
  client. Token blacklisting (or rotation) is the next step if needed.
- Throttle counters use the local in-process cache. With several workers each
  keeps its own counter, so production needs a shared cache such as Redis.
- Registration reveals whether an email already exists. Accepted for the MVP
  and mitigated by throttling.
- Passwords are validated with Django's standard validators. Email
  verification and password reset are not implemented yet.