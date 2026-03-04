# PR Evidence: Issue #52 - Harden World Memory (Fact Graph, Identities, and Relationships)

## Overview
This PR transitions the world memory architecture from text-based state storage to a structured, queryable **Fact Graph**. It introduces canonical identity normalization, ensuring consistent node linkage across disparate mentions (e.g., "The Blacksmith" and "a blacksmith" now merge to a single identity `blacksmith`), and enhances event ingestion to auto-extract typed relationship edges between entities.

## Changes Implemented
1. **Canonical Identity Normalization (`src/services/world_memory.py`)**:
   - Upgraded `_normalize_node_name` to aggressively strip articles ("the", "a", "an", "some") and handle whitespace/casing uniformly.
   - This ensures entities like "The Watchman" and "a watchman" map deterministically to the same `WorldNode`.

2. **Auto-Extracted Relationships (`WorldEdge`)**:
   - Modified `_record_graph_assertions` to intercept string-valued fact drafts.
   - If a fact asserts `{"subject": "player", "predicate": "friendship", "value": "companion"}` and the `companion` node exists, it now auto-creates a `WorldEdge` to strongly link the entities in the graph (in addition to creating the `WorldFact`).

3. **Typed Graph Query Helpers**:
   - Added `get_relationships(subject, target, type)` and `get_node_facts(node_name, predicate)` to provide strongly-typed programmatic graph traversals.
   - Upgraded `get_relevant_action_facts` to synthesize prompts from both structured relations and the standard `WorldFact` similarity.

## Verification
- Added `test_canonical_identity_merges_entity_names` demonstrating that structurally different surface forms correctly aggregate facts under the matching canonical node id.
- Added `test_fact_string_values_auto_extract_edges` demonstrating `WorldEdge` generation from string values linking known nodes.
- Full test suite `pytest tests/service/test_world_memory.py` successfully executed with 100% passing results, validating zero regressions on the existing fact extraction schema while seamlessly adopting the upgraded canonical entity linkage framework.

## Next Steps
With Deterministic Projections (Phase 1) and the Canonical Fact Graph (Phase 2) securely in place, the system is fully equipped to proceed to **Phase 3: Strict Action Validation (Issue #54)**, shifting the `command_interpreter` to rigorously enforce player actions against projected reality.
