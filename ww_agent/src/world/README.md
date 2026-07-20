# World boundary

`WorldWeaverClient` is the agent runtime's async HTTP boundary to the engine. `CityWorld` and
`CityTools` adapt that client to the protocols consumed by `CognitiveCore` and its effectors.

The client currently covers:

- resident bootstrap, scene polling, and new-event reads;
- typed world commands, travel, and narrator-free physical traces;
- world facts and grounding;
- direct-message threads and chat;
- map/navigation data;
- actor-scoped session lifecycle and federation travel.

The client deliberately has no generic session-variable or city-held identity-growth methods. A city is a
shared-world authority, not a storage or inspection surface for resident-private state.

Keep raw response-shape parsing here. Runtime modules should receive typed values or protocol-level
facts, not construct routes. Render scene/fact data as grounded prose without inventing people,
locations, capabilities, or events.

`CityWorld.post_map_move` opts resident prose movement into the engine's bounded sublocation fallback.
Canonical routes still win; only a clearly local, otherwise unknown destination can become an expiring
child of the current canonical node. Human map movement leaves that fallback off by default.

The removed `/api/next` narrative-turn path and generic `/api/action` fallback are not part of resident
cognition. Unsupported prose fails locally; world changes use typed commands and the canonical event spine.
