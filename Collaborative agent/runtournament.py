import os
from itertools import combinations

from bw4t.bw4tlogger import BW4TLogger
from bw4t.BW4TWorld import BW4TWorld, DEFAULT_WORLDSETTINGS
from bw4t.statistics import Statistics

from agents1.human import Human
from agents1.randomagent import RandomAgent


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
        {'name': 'agent1', 'botclass': RandomAgent, 'settings': {'slowdown': 1}},
        {'name': 'agent2', 'botclass': RandomAgent, 'settings': {'slowdown': 3}},
        {'name': 'human1', 'botclass': Human, 'settings': {'slowdown': 1}}
        ]
    teamsize=3

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
