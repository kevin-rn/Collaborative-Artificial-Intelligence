from abc import  ABC, abstractmethod
from matrx.agents.agent_utils.state import State # type: ignore
from matrx.agents import AgentBrain # type: ignore
from matrx.actions.object_actions import DropObject # type: ignore
from typing import final, List, Dict, Final, Set
from matrx.messages import Message # type: ignore
import traceback 

class BW4TBrain(AgentBrain, ABC):
    """
    This class is the obligatory base class for BW4T agents.
    BW4T agents must implement decide_on_bw4t_action
    """
        
    NOT_ALLOWED_PARAMS:Final[Set[str]] ={'remove_range', 'grab_range', 'door_range', 'action_duration'}
    
    DEFAULT_SETTINGS:Final[Dict[str,object]]={'slowdown':1, 'colorblind':False,'shapeblind':False}

    def __init__(self, settings:Dict[str,object]):
        '''
        @param settings contains the following key-values:
        * slowdown : integer. Basically this sets action_duration
        field to the given slowdown. 1 implies normal speed
        of 1 action per tick. 3 givs 1 allowed action every 3 ticks. etc
        Implementors of BW4TBrain are NOT ALLOWED TO CHANGE THIS VALUE.
        This is to ensure that agents run at the required speed.
        FIXME this is hacky. These parameters should really be private.
        * colorblind: bool. If true, all color info is removed from state
        * shapeblind: bool. if true, all shape info is removed from state 
        
        Missing values get the value from DEFAULT_SETTINGS.
        '''
        self.__settings = self.DEFAULT_SETTINGS.copy()
        self.__settings.update(settings)
        super().__init__()
    
    @final
    def initialize(self):
        super().initialize()
        self.__previous_tick_sent_messages:List[Message]=[]
        self.__drop_off_locations:List[tuple]=[]
        
    @final
    def decide_on_action(self, state:State):
        try:
            act,params = self.decide_on_bw4t_action(state)
        except:
            print("IGNORING ERROR FROM AGENT ")
            traceback.print_exc() 
            act,params=None,{}
            
        wrong = self.NOT_ALLOWED_PARAMS.intersection(set(params.keys()))
        if len(wrong) > 0:
            raise ValueError("Parameter use not allowed ", wrong)
        params['grab_range']=1
        # door_range=1 does not work, doors don't open
        #params['door_range']=1
        params['max_objects']=3
        params['action_duration'] = self.__settings['slowdown']
        
        self.__previous_tick_sent_messages=self.messages_to_send.copy()

        # WORKAROUND for issue in #30
        return act,params
    
    @final 
    def filter_observations(self,state:State)->State:
        newstate=state
        if self.__settings['colorblind']:
            newstate=state.state_update({id:self.__filterColor(vals) 
                for id,vals in state.items() })
        if self.__settings['shapeblind']:
            newstate=state.state_update({id:self.__filterShape(vals) 
                for id,vals in state.items() })

        try:
            res= self.filter_bw4t_observations(newstate)
        except:
            print("IGNORING ERROR FROM AGENT ")
            traceback.print_exc()
            res=newstate

        self.__previous_tick_sent_messages=self.messages_to_send.copy()
        return res
    
    
    def filter_bw4t_observations(self,state)->State:
        """ 
        Filters the world state before deciding on an action.
        This function is called every tick, so use this for message processing.

        In this method you filter the received world state to only those
        properties and objects the agent is actually supposed to see.

        Currently the world returns ALL properties of ALL objects within a
        certain range(s), as specified by :
        class:`matrx.agents.capabilities.capability.SenseCapability`. But
        perhaps some objects are obscured because they are behind walls and
        this agent is not supposed to look through walls, or an agent is not
        able to see some properties of certain objects (e.g. colour).

        The adjusted world state that this function returns is directly fed to
        the agent's decide function. Furthermore, this returned world state is
        also fed through the MATRX API to any visualisations.

        Override this method when creating a new AgentBrain and you need to
        filter the world state further.

        Parameters
        ----------
        state: State
            A state description containing all perceived
            :class:`matrx.objects.env_object.EnvObject` and objects inheriting
            from this class within a certain range as defined by the
            :class:`matrx.agents.capabilities.capability.SenseCapability`.

            The keys are the unique identifiers, as values the properties of
            an object. See :class:`matrx.objects.env_object.EnvObject` for the
            kind of properties that are always included. It will also contain
            all properties for more specific objects that inherit from that
            class.

            Also includes a 'world' key that describes common information about
            the world (e.g. its size).

        Returns
        -------
        filtered_state : State
            A dictionary similar to `state` but describing the filtered state
            this agent perceives of the world.

        Notes
        -----
        A future version of MATRX will include handy utility function to make
        state filtering less of a hassle (e.g. to easily remove specific
        objects or properties, but also ray casting to remove objects behind
        other objects)

        """
        return state
    
    @abstractmethod
    def decide_on_bw4t_action(self, state:State):
        '''
        @param state
        A state description as given by the agent's
        :meth:`matrx.agents.agent_brain.AgentBrain.filter_observation` method.

        Contains the decision logic of the agent.
        @return tuple (action name:str,  action arguments:dict)
        
        action is a string of the class name of an action that is also in the
        `action_set` class attribute. To ensure backwards compatibility
        we advise to use Action.__name__ where Action is the intended
        action.
        
        action_args is a dictionary with keys any action arguments and as values the
        actual argument values. If a required argument is missing an
        exception is raised, if an argument that is not used by that
        action a warning is printed. 
        
        An argument that is always possible is that of action_duration, which
        denotes how many ticks this action should take and overrides the
        action duration set by the action implementation. The minimum of 1
        is used if you provide a value <1.
            
        Check the action documentation to determine possible arguments.
        BW4T agents can not use NOT_ALLOWED_PARAMS above,
        they are set fixed by the environment builder
        
        This function is called only when the agent can take an action.
        Actions that need execution every tick should be placed in
        filter_bw4t_observations.
        '''
        pass
    
    def __filterColor(self, values:dict):
        '''
        removes colour from visualization attr. 
        Colors only appear in the visualization field.
        '''
        if not 'visualization' in values:
            return values
        newvis:dict = values['visualization'].copy()
        newvis.pop('colour')
        newvalues=values.copy()
        newvalues['visualization']=newvis
        return newvalues

    def __filterShape(self, values:dict)->dict:
        '''
        removes shape from visualization attr. 
        shapes only appear in the visualization field.
        '''
        if not 'visualization' in values:
            return values
        newvis:dict = values['visualization'].copy()
        newvis.pop('shape')
        newvalues=values.copy()
        newvalues['visualization']=newvis
        return newvalues
    
    @final
    def get_log_data(self):
        '''
        This will be called by gridworld to fetch additional data to log.
        Do not modify/override as this is used to assess agent performance
        '''
        data = {}

        # Add the agent's name for a nice reference
        data["agent_name"] = self.agent_name
        agentloc = self.state[self.agent_id]['location']
        if self.__drop_off_locations==[]:
            self.__drop_off_locations=[info['location'] 
                for info in self.state[{'is_goal_block':True}]]

        # Add a bool that is True when an object was dropped on a drop off location
        if self.previous_action == DropObject.__name__ \
            and agentloc in self.__drop_off_locations:
            data["dropped_block"] = 1
        else:
            data["dropped_block"] = 0

        # Add the number of sent messages
        data["prev_tick_messages"] = len(self.__previous_tick_sent_messages)

        return data