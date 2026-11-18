# 0003. Document storage and upload validation

## Context

Companies upload PDFs and text files that later feed the assistant. Files come
from untrusted users, belong to one organization, and are stored on local disk
in development and in S3 in production.

## Decisions

1. **Validate content, not just the name.** The extension and the declared
   content type are controlled by the client, so the bytes must match the
   claimed type: PDFs need the `%PDF-` signature, text files must be valid
   UTF-8 without null bytes. Size is capped at 10 MB and empty files are
   rejected.
2. **Opaque storage names.** Files are stored as
   `orgs/<organization>/documents/<uuid>.<ext>`. The user's filename is kept
   only as metadata after removing path components and control characters,
   which prevents path traversal and name collisions.
3. **Deduplicate by SHA-256 per organization**, enforced by a unique
   constraint. The same file in two organizations is allowed, since they must
   not know about each other.
4. **Nested URLs** (`/organizations/{id}/documents/`). The organization is
   resolved first from the user's memberships, so another company's
   organization or document answers 404.
5. **Roles**: any member can upload and read, only owners and admins delete.
6. **Downloads are streamed through the API**, so permissions are checked on
   every request. Responses are attachments with `nosniff`.
7. **Storage backend chosen by environment** (`USE_S3`): local disk for
   development, S3 with private objects in production. Tests use in-memory
   storage.
8. **Deletion removes the stored file after the database commit**, so a failed
   transaction never leaves a row pointing to a missing file.

## Consequences and limits

- Django reads the whole upload before validation can reject it. In
  production a reverse proxy must also cap the request body size.
- No antivirus scanning yet. Files are never executed or served inline, which
  limits the risk, but scanning is the next step for a public service.
- Deleting an organization removes its rows but not its files. A cleanup job
  is needed.
- Streaming downloads through the API uses worker time. Presigned S3 URLs
  would scale better at the cost of links that work without authentication
  until they expire.
- Only PDF, TXT and Markdown are supported. Word documents need another
  parser and signature check.