# Finish the public commons client cutover

## Status

The new `client-public` already provides the intended front door: `look around` or `join the world`, a
sessionless walkabout, native registration and login, a place-centered map, concrete movement and object
actions, and local presence. Its API intentionally omits shard-wide resident telemetry.

The remaining work is to make this the normal human interface and retire the old combined client as a
public product.

## Update (2026-07-18)

The root defaults now use `client-public`. `weave-up`, `weave-client`, and `client` start the place-centered
commons client on port 5174, and the default client Compose project builds from `client-public/`. The old
combined interface is no longer launched by a normal development or deployment command; it remains
temporarily available as the explicitly named local `client-legacy` command while the useful parts are
sorted from the telemetry and obsolete controls.

The action inventory found real participant gaps still to review: correspondence, direct invitations and
revocation with a safe encounter target, and human cross-node travel. Their presence in
the old client does not automatically mean every old interaction should be copied. Each should use the
current typed engine contract and fit the place-centered interface.

The first parity slice now covers the complete typed stoop custody loop and witnessed exchange. A person at
the exact place can reclaim an object they left, give a carried object to a co-present recipient already
identified by the exchange contract, make an exact swap offer, and accept, decline, or cancel an open
offer. Sessionless looking still exposes no custody controls. The public client does not gain a general
session roster merely to make recipient selection convenient; giving to a co-present person who carries
nothing still needs a safer encounter-target contract.

The next slice brings ordinary door rules into the same place panel. A visitor looking at a controlled
place can read its note and knock when requests are allowed. The controller can change that one door's
rule and answer pending knocks. This is deliberately not a town-wide
permissions screen. Pending knocks now remain pending in the typed status response, so refreshing the page
does not offer a duplicate request.

The supported path now also has explicit labels for join fields, visible keyboard focus, keyboard-operable
map places, focus handoff when a place opens, and reduced-motion behavior for both CSS and map movement.
The mobile place sheet uses more of the usable viewport and keeps form controls at a readable touch size.

Password recovery now uses the current actor-auth routes in the public join card. A reset link arriving at
the site opens the reset form directly, and a successful reset creates a normal local session. The request
response does not reveal whether an account exists. Actual delivery still depends on the node configuring
its optional email provider.

## Build next

1. Port only ordinary participant actions that fit the place-centered design, including correspondence and
   cross-node travel when those contracts are ready.
2. Decide whether any old-client view has a justified steward use. Move such functions behind the private
   operations boundary in Major 71.
3. Remove or archive the remaining guild, observer-dashboard, narrator, model-setting, and resident
   telemetry UI rather than carrying it forward.
4. Add browser-level accessibility checks once the public client has a browser test harness; source-contract
   guards and the production TypeScript build cover the current keyboard, labeling, mobile, and low-motion
   implementation in the meantime.

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
- [ ] Accessibility and mobile checks cover the supported entry and place flows. Static guards exist;
  browser and screen-reader checks do not yet.
