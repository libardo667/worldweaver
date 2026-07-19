# Finish the public commons client cutover

## Status

The new `client-public` already provides the intended front door: `look around` or `join the world`, a
sessionless walkabout, native registration and login, a place-centered map, concrete movement and object
actions, local presence, and an optional activity log. Its API intentionally omits shard-wide resident
telemetry.

The remaining work is to make this the normal human interface and retire the old combined client as a
public product.

## Update (2026-07-18)

The root defaults now use `client-public`. `weave-up`, `weave-client`, and `client` start the place-centered
commons client on port 5174, and the default client Compose project builds from `client-public/`. The old
combined interface is no longer launched by a normal development or deployment command; it remains
temporarily available as the explicitly named local `client-legacy` command while the useful parts are
sorted from the telemetry and obsolete controls.

The action inventory found real participant gaps still to review: password recovery, correspondence,
giving and exchange, ordinary room access, stoop withdrawal, and human cross-node travel. Their presence in
the old client does not automatically mean every old interaction should be copied. Each should use the
current typed engine contract and fit the place-centered interface.

## Build next

1. Inventory actions still available only in the old client.
2. Port only ordinary participant actions that fit the place-centered design, including correspondence and
   cross-node travel when those contracts are ready.
3. Decide whether any old-client view has a justified steward use. Move such functions behind the private
   operations boundary in Major 71.
4. Remove or archive the remaining guild, observer-dashboard, narrator, model-setting, and resident
   telemetry UI rather than carrying it forward.
5. Make the root development command, deployment docs, and public node serve `client-public` by default.
6. Add keyboard, screen-reader, mobile, and low-motion checks to the supported path.

## Boundaries

- The map, current place, and available actions are the default experience.
- A text-forward or accessible view may exist, but it uses the same typed actions.
- Watching a place does not expose private resident histories, prompts, rest reasons, wake times, or queues.
- Steward operations and City Studio are separate authenticated products.
- No narrator model, personal inference key, guild role, or payment gate returns to public onboarding.

## Acceptance criteria

- [x] The first screen offers only `look around` and `join the world`.
- [x] A visitor can inspect places without an account or shard-wide telemetry.
- [x] A participant can register, log in, bootstrap a session, move, speak, make, and use object stoops.
- [x] The map and current place are primary; activity history is optional.
- [ ] All supported ordinary participant actions are available in `client-public`.
- [ ] The old combined client is either removed or limited to named steward-only functions.
- [x] Root commands and deployment serve the public client as the default human surface.
- [ ] Accessibility and mobile checks cover the supported entry and place flows.
