# Make human accounts email-first and choose a name after verification

## Status

The current registration card asks for an email address, a username, and a display name in one crowded
step. A live Alderbank check produced an account whose internal username was `tester` and whose public name
was `ww`; the person using it did not remember choosing `ww` as their name. The server faithfully stored
the submitted fields, so the failure is the account design and form, not a random presence bug.

WorldWeaver does not currently verify email addresses. Registration immediately creates an active actor,
issues a login token, and sends an optional welcome email. The isolated Alderbank node currently has no
email-delivery provider configured, so a verification requirement cannot be switched on honestly until
delivery and recovery are ready.

The first safe migration slice is live. An authenticated existing account can now correct its public display
name from the account panel. The update changes the canonical federation actor, local player projection, and
current city session without changing actor ID or world state. The route, client panel, and immutable engine
image were deployed to isolated Alderbank on 2026-07-19. Registration and verification are still unchanged.

## Problem

People should not need both a username and an email address to enter this project. The extra username has
no useful human-facing purpose, and asking for a public name before the email account is established mixes
authentication with identity in a confusing way.

The desired flow is:

1. register with email, password, and password confirmation;
2. verify control of the email address;
3. choose a public display name;
4. enter a city;
5. later log in with email and password.

The federation code still has legacy `username` and `handle` fields. They may remain as private compatibility
columns during migration, but they must not appear in the human form or become a second login identity.

## Proposed solution

1. Change public registration to accept email, password, password confirmation, and terms acceptance. Login
   and password reset accept email only.
2. Generate any required legacy username internally from the account ID or a hash. Never show it as a
   participant identity and never derive the public name from the email address.
3. Add a durable, one-use email-verification record at the federation identity authority. Store only a hash
   of the token, give it a short expiry, and support an explicitly rate-limited resend.
4. Send verification links through the configured email provider. A node that requires verification must
   report mail delivery as a startup requirement rather than creating accounts that can never be verified.
5. After verification, present a small separate form for the public display name. Updating it changes the
   canonical federation actor and each local player projection without changing actor ID, correspondence,
   objects, or travel state.
6. Refuse city-session bootstrap while a new account is unverified or has no completed public profile.
   Authentication may still issue a limited token so the person can verify, resend, or finish the profile.
7. Grandfather existing accounts as verified. Give them an authenticated profile screen where they can
   review and correct their public name.
8. Keep public names non-unique unless a concrete abuse or addressing requirement proves otherwise. Stable
   actor IDs, not names, distinguish people internally.
9. Remove the old username-or-email wording, username field, and display-name field from the first
   registration step. Use visible labels and plain error messages rather than placeholder-only fields.

## Files affected

- `worldweaver_engine/src/models/__init__.py`
- `worldweaver_engine/src/api/auth/routes.py`
- `worldweaver_engine/src/api/federation/routes.py`
- `worldweaver_engine/src/services/federation_identity.py`
- `worldweaver_engine/src/services/email_service.py`
- `worldweaver_engine/src/api/game/state.py`
- `worldweaver_engine/client-public/src/components/JoinFlow.tsx`
- `worldweaver_engine/client-public/src/api/ww.ts`
- `worldweaver_engine/client-public/src/api/types.ts`
- `worldweaver_engine/client-public/src/session/store.ts`
- `worldweaver_engine/tests/`
- `docs/`

## Boundaries

- Email addresses and verification state are private authentication data, never world presence.
- Public names do not become permanent handles or ownership claims.
- A shard does not become the owner of an account merely because registration happened there.
- Verification tokens are hashed at rest, expire, are one-use, and never appear in normal logs.
- Password confirmation is checked before account creation; the password itself is never logged.
- Existing accounts and old federation projections remain readable during the migration.
- Do not enable mandatory verification on a public node until delivery, resend, expiry, and recovery have
  all been tested.

## Acceptance criteria

- [ ] The public registration form asks only for email, password, password confirmation, and terms.
- [ ] Login and password reset ask for email, not username-or-email.
- [ ] A mismatched password confirmation cannot create an account.
- [ ] Registration creates a hashed, expiring, one-use verification token and sends a working link.
- [ ] An unverified account cannot bootstrap a city session.
- [ ] A verified account without a display name is taken to display-name setup rather than into the city.
- [x] Setting or changing a display name updates the canonical actor and local projection without changing
  actor ID or world state.
- [x] Existing accounts can log in and correct their public name.
- [ ] The UI no longer exposes the legacy username or uses it as a login identifier.
- [ ] Verification resend is rate-limited and does not reveal whether an unrelated email has an account.
- [ ] A node configured to require verification fails readiness clearly when email delivery is unavailable.
- [ ] Federation, session bootstrap, travel, password reset, and auth rate-limit tests pass.

## Risks and rollback

Turning verification on before email delivery works would lock people out. Keep the current account reader
and grandfathering rule during rollout, deploy the schema and email path first, then the new client, and only
then require verification for newly created accounts. If delivery fails, pause new registration rather than
silently marking unverified addresses as trusted.
