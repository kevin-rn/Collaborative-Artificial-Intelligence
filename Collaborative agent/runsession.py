import os

from bw4t.bw4tlogger import BW4TLogger
from bw4t.BW4TWorld import BW4TWorld
from bw4t.statistics import Statistics

from setuptools.sandbox import save_path  # type: ignore

from agents1.human import Human
from agents1.randomagent import RandomAgent
from agents1.Team19Agent import Team19Agent
from agents1.Team2Agent import Team2Agent
from agents1.Team45Agent import Team45Agent

"""
This runs a single session. You have to log in on localhost:3000 and 
press the start button in god mode to start the session.
"""

if __name__ == "__main__":
    agents = [ 
        # {'name': 'Team19agent1', 'botclass': Team19Agent, 'settings': {}},
        # {'name': 'Team19agent2', 'botclass': Team19Agent, 'settings': {}}

        {'name': 'Team19agent1', 'botclass': Team19Agent, 'settings': {'colorblind':True}},
        {'name': 'Team45agent2', 'botclass': Team45Agent, 'settings': {'shapeblind':True}},
        # {'name': 'Team19agent3', 'botclass': Team19Agent, 'settings': {'slowdown':1}}

        # {'name': 'Team19agent1', 'botclass': Team19Agent, 'settings': {'colorblind':True}},
        # {'name': 'Team19agent2', 'botclass': Team19Agent, 'settings': {'shapeblind':True}}
    ]
    print("Started world...")
    world = BW4TWorld(agents).run()
    print("DONE!")
    print(Statistics(world.getLogger().getFileName()))
