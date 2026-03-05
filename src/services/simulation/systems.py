from abc import ABC, abstractmethod
from typing import Optional

from ...models.schemas import ActionDeltaContract, ActionDeltaIncrementOperation
from ..state_manager import AdvancedStateManager


class SimulationSystem(ABC):
    """
    Base contract for a deterministic subsystem.
    A system observes the world state and proposes deltas without applying them directly.
    """
    
    @property
    @abstractmethod
    def system_id(self) -> str:
        """Unique identifier for this subsystem."""
        pass
    
    @abstractmethod
    def evaluate(self, state_manager: AdvancedStateManager) -> Optional[ActionDeltaContract]:
        """
        Evaluate current state and propose changes for this tick.
        Return None if no changes are needed.
        """
        pass


class EnvironmentDegradationSystem(SimulationSystem):
    """
    Simulates gradual environmental degradation/drift over consecutive turns.
    Increases ambient danger slightly over time to ensure narrative pressure.
    """
    
    @property
    def system_id(self) -> str:
        return "sys_environment_degradation"
        
    def evaluate(self, state_manager: AdvancedStateManager) -> Optional[ActionDeltaContract]:
        # Only start degrading if tension or danger is already non-zero (world is somewhat established)
        current_danger = state_manager.get_variable("environment.danger_level", 0.0)
        
        # We don't want to blindly force danger up if it's a peaceful scenario, 
        # so this is just a subtle drift mechanic. Let's add 0.1 danger per turn.
        # It's a very slow creep.
        if current_danger > 0.0 and current_danger < 8.0:
            return ActionDeltaContract(
                increment=[
                    ActionDeltaIncrementOperation(key="environment.danger_level", amount=0.1)
                ],
                append_fact=[],
                set=[],
                delete=[]
            )
            
        return None
