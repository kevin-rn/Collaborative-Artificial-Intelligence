import os
from itertools import combinations

from bw4t.bw4tlogger import BW4TLogger
from bw4t.BW4TWorld import BW4TWorld, DEFAULT_WORLDSETTINGS
from bw4t.statistics import Statistics

from agents1.human import Human
from agents1.randomagent import RandomAgent
from agents1.Team19Agent import Team19Agent
from agents1.Team2Agent import Team2Agent
from agents1.Team45Agent import Team45Agent

"""
This runs a single session. You have to log in on localhost:3000 and 
press the start button in god mode to start the session.
"""


def checkNoDuplicates(names:list):
    '''
    @raise ValueError if there is a duplicate in names list: 
    '''
    duplicates=[name for name in names if names.count(name) > 1]
    if len(duplicates) >0:
        raise ValueError(f"Found duplicate agent names {duplicates}!")

if __name__ == "__main__":
    agents = [
        # {'name':'agent2', 'botclass':RandomAgent, 'settings':{'slowdown':1, 'colorblind':True}},
        # {'name':'agent3', 'botclass':RandomAgent, 'settings':{'slowdown':1, 'shapeblind':True}}
        # {'name':'human1', 'botclass':Human, 'settings':{'shapeblind':True}}
        # {'name': 'Team19agent1', 'botclass': Team19Agent, 'settings': {}},
        # {'name': 'Team19agent2', 'botclass': Team19Agent, 'settings': {}}

        {'name': 'Team19agent1C', 'botclass': Team19Agent, 'settings': {'colorblind':True}},
        {'name': 'Team19agent2S', 'botclass': Team19Agent, 'settings': {'shapeblind':True}},
        # {'name': 'Team19agent3', 'botclass': Team19Agent, 'settings': {'slowdown':1}},
        # {'name': 'Team45agent1C', 'botclass': Team45Agent, 'settings': {'colorblind':True}},
        # {'name': 'Team45agent2S', 'botclass': Team45Agent, 'settings': {'shapeblind':True}},
        # {'name': 'Team45agent3', 'botclass': Team45Agent, 'settings': {'slowdown':1}},
        {'name': 'Team2agent1C', 'botclass': Team2Agent, 'settings': {'colorblind':True}},
        {'name': 'Team2agent2S', 'botclass': Team2Agent, 'settings': {'shapeblind':True}},
        # {'name': 'Team2agent3', 'botclass': Team2Agent, 'settings': {'slowdown':1}},
        # {'name': 'Team19agent3', 'botclass': Team19Agent, 'settings': {}}
        # {'name': 'Team19agent2', 'botclass': Team19Agent, 'settings': {'shapeblind':True}},
        # {'name': 'Team45Agent', 'botclass': Team45Agent, 'settings': {'shapeblind':True}}
        # {'name': 'Team2Agent', 'botclass': Team2Agent, 'settings': {'shapeblind':True}}

    ]
    teamsize=2

    # safety check: all names should be unique 
    # This is to avoid failures halfway the run.
    checkNoDuplicates(list(map(lambda agt:agt['name'], agents)))

    settings = DEFAULT_WORLDSETTINGS.copy()
    settings['matrx_paused']=False

    for team in combinations(agents,teamsize):
        print(f"Started session with {team}")

        world=BW4TWorld(list(team),settings).run()
        print(Statistics(world.getLogger().getFileName()))

    print("DONE")
