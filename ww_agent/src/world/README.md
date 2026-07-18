# World boundary

`WorldWeaverClient` is the agent runtime's async HTTP boundary to the engine. `CityWorld` and
`CityTools` adapt that client to the protocols consumed by `CognitiveCore` and its effectors.

The client currently covers:

- resident bootstrap, scene polling, and new-event reads;
- action submission through `/api/action`;
- world facts and grounding;
- direct-message threads and chat;
- map/navigation data;
- identity-growth synchronization and session variables.

Keep raw response-shape parsing here. Runtime modules should receive typed values or protocol-level
facts, not construct routes. Render scene/fact data as grounded prose without inventing people,
locations, capabilities, or events.

`CityWorld.post_map_move` opts resident prose movement into the engine's bounded sublocation fallback.
Canonical routes still win; only a clearly local, otherwise unknown destination can become an expiring
child of the current canonical node. Human map movement leaves that fallback off by default.

The removed `/api/next` narrative-turn path is not part of this runtime. New event ingestion and action
submission should converge on the canonical world-event spine described by the active architecture
plan.
