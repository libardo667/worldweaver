# Runtime Critical Path Map (Stage 2)

## API Entry Surface
- App entry: [main.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/main.py)
- Game router composition: [src/api/game/__init__.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/api/game/__init__.py)
- Core gameplay endpoints:
1. `POST /api/next` in [story.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/api/game/story.py:59)
2. `POST /api/action` in [action.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/api/game/action.py:118)
3. `POST /api/action/stream` in [action.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/api/game/action.py:172)
4. `POST /api/turn` in [turn.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/api/game/turn.py:43)

## Canonical Mutation Spine
- Turn orchestration authority: [TurnOrchestrator](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/services/turn_service.py:379)
- Action mutation path:
1. `process_action_turn` acquires state manager: [turn_service.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/services/turn_service.py:383)
2. canonical state commits via `reduce_event`: [turn_service.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/services/turn_service.py:568)
3. world event write via `world_memory.record_event`: [turn_service.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/services/turn_service.py:593)
- Next mutation path:
1. `process_next_turn` acquires state manager: [turn_service.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/services/turn_service.py:781)
2. choice/vars/system tick via `reduce_event`: [turn_service.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/services/turn_service.py:808)
3. selected storylet event write via `world_memory.record_event`: [turn_service.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/services/turn_service.py:1173)

## Core Runtime Dependency Chains
- `/api/next`:
1. request lock via `session_mutation_lock`
2. `TurnOrchestrator.process_next_turn`
3. storylet selection via [storylet_selector.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/services/storylet_selector.py:154)
4. state persistence via [session_service.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/services/session_service.py:171)
5. best-effort prefetch schedule via [prefetch_service.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/services/prefetch_service.py:592)
- `/api/action` and `/api/action/stream`:
1. request lock via `session_mutation_lock`
2. `TurnOrchestrator.process_action_turn`
3. reducer commit + world event logging
4. best-effort prefetch schedule
- `/api/turn`:
1. feature-flag gated unified endpoint
2. delegates to same `TurnOrchestrator` action/next paths
3. keeps prefetch behavior aligned with split endpoints

## Supporting Runtime Paths
- State/session admin endpoints in [state.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/api/game/state.py)
- Spatial navigation/movement in [spatial.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/api/game/spatial.py:103)
- World history/facts/projection reads in [world.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/api/game/world.py:23)
- Prefetch trigger/status in [prefetch.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/api/game/prefetch.py:21)
- Runtime model/settings control in [settings_api.py](C:/Users/levib/PythonProjects/worldweaver/worldweaver/src/api/game/settings_api.py:84)

## High-Leverage Pruning Zones (Mapping Only, No Decisions Yet)
- Duplicate ingress paths (`/api/next` + `/api/action` + `/api/turn`) with overlapping orchestration.
- State/session maintenance surface in `state.py` (broad responsibilities in one module).
- Prefetch and projection plumbing crossing selection + turn orchestration + diagnostics.
- Compatibility exports and test-only aliases in router/state modules.

## Do-Not-Prune-First Zones
- Reducer commit pipeline in `turn_service.py`.
- Session persistence and lock discipline in `session_service.py`.
- World event/projection store logic in `world_memory.py`.
- Request correlation and route timing middleware in `main.py`.
