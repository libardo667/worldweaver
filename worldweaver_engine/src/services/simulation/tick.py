import logging
from typing import List

from ...config import settings
from ...models.schemas import ActionDeltaContract
from ..state_manager import AdvancedStateManager
from .systems import SimulationSystem, EnvironmentDegradationSystem

logger = logging.getLogger(__name__)

# Registry of active simulation systems
_ACTIVE_SYSTEMS: List[SimulationSystem] = [
    EnvironmentDegradationSystem(),
]


def tick_world_simulation(state_manager: AdvancedStateManager) -> ActionDeltaContract:
    """
    Orchestrate a deterministic world tick across all registered subsystems.
    Aggregates proposed changes into a single composable delta contract.
    Does not apply them directly.
    """
    aggregated_delta = ActionDeltaContract()

    if not settings.enable_simulation_tick:
        return aggregated_delta

    for system in _ACTIVE_SYSTEMS:
        try:
            proposed = system.evaluate(state_manager)
            if proposed:
                # Merge increments
                aggregated_delta.increment.extend(proposed.increment)
                # Merge sets
                aggregated_delta.set.extend(proposed.set)
                # Merge facts
                aggregated_delta.append_fact.extend(proposed.append_fact)
                # Merge deletes
                aggregated_delta.delete.extend(proposed.delete)

                logger.debug(f"[Simulation] System '{system.system_id}' proposed {len(proposed.increment)} increments, {len(proposed.set)} sets")

        except Exception as e:
            logger.error(f"[Simulation] System '{system.system_id}' threw exception during eval: {e}", exc_info=True)

    return aggregated_delta
