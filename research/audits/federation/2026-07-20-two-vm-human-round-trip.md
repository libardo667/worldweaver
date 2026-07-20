# Two-VM human travel proof

Date: 2026-07-20

Runtime image commit: `55e7e523b100729e026887c6f3fe883ee1f53d4b`

Operator fix commit: `2b8fc9f`

## Result

A synthetic human traveled from San Francisco to Portland and back through the normal account, session,
route-discovery, departure, and arrival APIs. The two cities ran in separate Ubuntu 24.04 KVM guests with
separate kernels, disks, Docker daemons, databases, node folders, secrets, and signing keys.

The round trip passed. Only the returned San Francisco session remained live. Portland had no live copy. The
directory recorded both trips as `arrived` and attached the actor to San Francisco.

This is independent-host evidence on one physical computer. It is not the remaining two-computer HTTPS proof.

## Topology

```text
Ubuntu VM 1 (192.168.77.1)          Ubuntu VM 2 (192.168.77.2)
  closed directory :9000              Portland :8003
  San Francisco :8002                 separate Docker daemon
  separate Docker daemon

             private QEMU Ethernet link
```

QEMU gave each guest its own machine ID and boot ID. Node traffic crossed the private guest-to-guest link; it
did not use a shared Docker network or `host.docker.internal`. Only each guest's SSH port was forwarded to the
host loopback interface.

All 13 pre-existing development and public containers were stopped cleanly before the test. Their named
volumes were not deleted. No resident container was started, and no resident files or inference credentials
were copied into the lab.

## Setup proof

- The directory, San Francisco, and Portland were generated as standalone node folders outside the source
  checkout.
- The folders referenced immutable published engine and agent images for commit `55e7e52`.
- VM 1 pulled and ran the directory and San Francisco folders. VM 2 independently pulled and ran Portland.
- The directory started in closed mode and admitted the two public `node.json` descriptors with written
  reasons before either city registered.
- Both cities registered with their own Ed25519 key, sent fresh pulses, and appeared healthy at their declared
  private-network URL.
- The final proof run had no shared `FEDERATION_TOKEN` in the directory or either city. After all three
  services were recreated, registration, pulses, discovery, travel, and return continued through signed node
  requests.
- VM 1 reached Portland directly. VM 2 reached San Francisco and the directory directly.
- Agents remained stopped throughout.

San Francisco seeded 1,317 places. Portland seeded 1,315 places. Both one-time reset endpoints were then
disabled by their folder-local seed command.

## Round-trip proof

The final test created a new synthetic human account in San Francisco. Its actor ID was
`e5b0d9ba-7ce0-480c-af57-f933945cd4c0`.

1. The account entered San Francisco at Embarcadero.
2. It used route `sf-portland-coast-starlight` to depart for node `pdx-vm2`.
3. San Francisco retired the source session before Portland accepted the actor.
4. The same account logged in on Portland through the shared directory identity and arrived at Pearl
   District with the same actor ID.
5. It used route `portland-sf-coast-starlight` to return to node `sfo-vm1`.
6. Portland retired its session before San Francisco accepted the actor at Embarcadero.
7. Repeating each departure and arrival returned the existing result rather than creating another trip or
   session.

Final checks found:

| Check | Result |
| --- | --- |
| live San Francisco sessions for the actor | one: the returned session |
| live Portland sessions for the actor | zero |
| directory actor state | `active` on `sfo-vm1` |
| outbound directory trip | `sfo-vm1 -> pdx-vm2 -> arrived` |
| return directory trip | `pdx-vm2 -> sfo-vm1 -> arrived` |

## Directory outage proof

The directory database and API were then stopped while both cities remained online.

- Both city health endpoints continued to answer normally.
- Both discovery endpoints reported the configured directory as unreachable and returned no hosted
  destinations instead of stale availability.
- The tested human's final San Francisco session remained live.
- Restarting the directory preserved its admission records, and fresh signed pulses restored both cities.

This proves the tested local-life and discovery behavior for a complete directory outage. It does not cover a
directory failure in the middle of a departure or arrival.

## Trust failure proof

The Portland backend signed a registration request with its own key while claiming the already admitted San
Francisco node ID. The closed directory rejected the request with HTTP 403. San Francisco and Portland kept
their original keys, URLs, admission state, and fresh pulses.

This exposed and fixed a separate operator bug before the proof: an Ed25519 public key may validly begin with
`-`. The folder operator previously passed such a key as a separate command-line token, which `argparse`
mistook for an option. It now uses the unambiguous `--public-key=<key>` form, with a regression test.

## Other implementation work found by the setup

The node generator previously assumed every backend listened only on loopback and advertised
`http://localhost:<port>`. Those are good defaults for a local node behind an explicit ingress, but they made
an isolated private-node network require manual Compose edits. The generator now has explicit
`--bind-address`, `--public-url`, and `--client-url` options. It validates those values and keeps
`127.0.0.1` as the default. The Cloudflare operator check still refuses a non-loopback backend.

The full workspace gate after this change passed 553 engine tests and 475 agent tests, both web builds, and
all lint and formatting checks.

## What this does not prove

- The two guests were on one physical WSL computer and were operated by one person.
- Node traffic used private HTTP, not independently issued HTTPS certificates.
- No packet crossed the public internet or a residential router/NAT boundary.
- The test did not interrupt the directory, source, or destination during a handoff.
- It used a human actor. Resident travel still needs the actor-scoped resident/host capability described in
  Major 37.
- It did not test off-device backup restore, address rotation, or an unavailable former host.

The next network proof should repeat the same human round trip between two separately administered HTTPS
addresses on different computers or genuinely separate trust domains, then inject outages at each handoff
stage.
