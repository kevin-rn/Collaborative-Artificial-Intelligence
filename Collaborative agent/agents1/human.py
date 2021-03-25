from matrx.agents.agent_types.patrolling_agent import PatrollingAgentBrain # type: ignore
from matrx.actions import MoveNorth, OpenDoorAction, CloseDoorAction # type: ignore 
from matrx.actions.move_actions import MoveEast, MoveSouth, MoveWest # type: ignore 
import numpy as np # type: ignore 
import random # type: ignore 
from matrx.agents.agent_utils.state import State # type: ignore 

from bw4t.BW4TBrain import BW4TBrain
from matrx.agents import HumanAgentBrain # type: ignore

class Human(HumanAgentBrain):
    '''
    Human that can also handle slowdown. Currently not really implemented,
    we take the parameter but ignore it.
    '''
    def __init__(self, slowdown:int):
        super().__init__()
    
