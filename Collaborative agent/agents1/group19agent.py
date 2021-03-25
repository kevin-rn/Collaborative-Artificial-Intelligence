from typing import List, Dict
import numpy as np  # type: ignore
from matrx.actions import MoveNorth, OpenDoorAction, CloseDoorAction, GrabObject, DropObject  # type: ignore
from matrx.actions.move_actions import MoveEast, MoveSouth, MoveWest  # type: ignore
from matrx.agents.agent_utils.state import State  # type: ignore

from bw4t.BW4TBrain import BW4TBrain
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state_tracker import StateTracker

from matrx.messages import Message
from agent_utils.block import Block

import random

FORMAT_BLOCK_MSG_SEND: str = "{{{0}: {{" \
                             "'obj_id':{0}," \
                             "'location': {1}," \
                             "'carried_by': {2}, " \
                             "'colour': {3}, " \
                             "'shape': {4}" \
                             "}}" \
                             "}}"


class Group19Agent(BW4TBrain):
    """
    This is group 19's agent
    """

    def __init__(self, settings: Dict[str, object]):
        super().__init__(settings)
        self._moves = [MoveNorth.__name__, MoveEast.__name__, MoveSouth.__name__, MoveWest.__name__]

    def initialize(self):
        super().initialize()
        self._door_range = 1
        self.state_tracker = StateTracker(agent_id=self.agent_id)
        self.navigator = Navigator(agent_id=self.agent_id, action_set=self.action_set,
                                   algorithm=Navigator.A_STAR_ALGORITHM)

        self.firstTick = True
        self.skipTick = False

        # self.update_waypoint([(18,8)])
        self.block_objective = None
        self.collect_block_objective = None
        # self.found_blocks = {}
        self.collect_blocks: Dict[str, Block] = {}
        self.collect_blocks_completed = []
        # self.blocks_set_beside_collect_block = []
        # self.collect_blocks_completed = {}
        # self.holding_collect_blocks = {}
        self.holding_blocks: Dict[str, Block] = {}
        # self.known_blocks = []
        self.msgQueue = []
        self.one_step_right_bool = False
        self.blocks_dict: Dict[str, Block] = {}
        self.block_sent_list: Dict[str, Block] = {}
        self.just_dropped_off = []

    def filter_bw4t_observations(self, state):
        objects = list(state.keys())
        if self.firstTick:
            # agentLoc = state[self.agent_id]['location']
            # i = agentLoc[0] - 1
            # locs = [(18, 3), (6, 14), (18, 8)]
            # self.update_waypoint([locs[i]])

            loc = self.choose_room(state)
            self.update_waypoint(loc)

            self.firstTick = False
            self.get_collect_blocks(state, objects)

        self.update_block_dict(state, objects)


        for msg in self.received_messages:
            print("new message", self.agent_id)
            print(msg)
            msg_to_block = Block.str_to_block(msg)

            # adding message of a Block to the blocks list
            # only if block is not already in blocks list and not none
            if msg_to_block is not None:

                # Check for block placement by others
                if msg_to_block.get_location() in [self.collect_blocks.get(block).get_location() for block in self.collect_blocks]:
                    print("new completed", self.find_collect_block(msg_to_block), msg_to_block)
                    self.collect_blocks_completed.append(self.find_collect_block(msg_to_block))

                msg_key = msg_to_block.get_obj_id()
                block_in_list = self.blocks_dict.get(msg_key, None)
                if block_in_list is None:
                    self.blocks_dict.update({msg_key: msg_to_block})
                else:

                    oldBlock = self.blocks_dict[msg_key]
                    newBlock = self.blocks_dict[msg_key] + msg_to_block
                    if msg_to_block.get_carried_by() and oldBlock.get_carried_by():
                        if oldBlock.get_carried_by()[0] < msg_to_block.get_carried_by()[0]:
                            newBlock.set_carried_by(oldBlock.get_carried_by())
                        else:
                            self.block_objective = None
                            newBlock.set_carried_by(msg_to_block.get_carried_by())
                    self.blocks_dict.update({msg_key: newBlock})
                self.block_sent_list.update({msg_key: self.blocks_dict[msg_key]})


        # print blocks as strings. TODO: REMOVE THIS AFTER TESTING!
        print(f"Blocks list:" + self.agent_id)
        if len(self.blocks_dict) != 0:
            [print(obj, v) for obj, v in self.blocks_dict.items()]
        else:
            print("self.blocks_list empty")

        if not self.one_step_right_bool:
            self.check_for_block_of_interest_and_go_to_it(state, objects)
            if self.block_objective is None:
                self.collect_block_objective = self.get_first_collect_block()
                if self.collect_block_objective is not None:
                    self.update_waypoint([self.collect_block_objective.get_location()])

        for block in self.blocks_dict.values():
            if block.get_obj_id() not in self.block_sent_list.keys() or self.block_sent_list.get(
                    block.get_obj_id()) != block:
                # add to list to keep track of what has already been sent
                self.block_sent_list.update({block.get_obj_id(): block})
                # convert to msg string format
                msg = self.dict_to_str_block(block)
                print("sending message", msg, self.agent_id)
                self.send_message(Message(content=msg, from_id=self.agent_id))

        while len(self.msgQueue) > 0:
            msg = self.msgQueue.pop(0)
            self.send_message(Message(content=msg, from_id=self.agent_id))

        # empty received messages (because of this bug: https://github.com/matrx-software/matrx/issues/240)
        self.received_messages = []
        return state  # Why need to returning state

    def decide_on_bw4t_action(self, state: State):
        # blocks = state.get_of_type('CollectableBlock')

        action = self.open_nearby_doors(state)
        if action is not None:
            return action

        action = self.get_action(state)
        # print("action:", action, self.agent_id)
        if action is None and self.block_objective is not None:
            action = self.grab_block_and_go_to_first_drop_off_point(state)
        elif action is None and self.collect_block_objective is not None:
            # print(self.collect_block_objective, self.agent_id)
            action = self.drop_block_and_go_to_next_drop_off_point(state)
        elif action is None:
            # self.update_waypoint([(1, 1)])
            loc = self.choose_room(state)
            self.update_waypoint(loc)
            action: tuple = (action, {})
        else:
            action: tuple = (action, {})

        return action

    def get_closest_block_to_agent(self, state: State):
        """
        Calculates the distance of the agent to all the blocks known until now
        and return list of distances sorted from small to large distances
        :param state: state object to fetch agents location from
        :return: list of distances sorted from small to large distances
        """
        dist_to_blocks = []

        # for each seen block, calculate dist of agent to the block
        for block in self.blocks_dict.values():
            curr_block_dist = np.linalg.norm(
                np.array(block.get_location()) - np.array(
                    state[self.agent_id]['location']))
            dist_to_blocks.append(curr_block_dist)

        return dist_to_blocks

    def check_for_block_of_interest_and_go_to_it(self, state, objects):
        # print("check block of interest", self.agent_id)

        if self.blocks_dict:
            distance_list = self.get_closest_block_to_agent(state)
            distance_list_sorted_indexes = sorted(range(len(distance_list)), key=lambda k: distance_list[k])
            # print(distance_list)
            # print(distance_list_sorted_indexes)
            for dist_index in distance_list_sorted_indexes:
                # index_found_block = distance_list.index(dist)
                found_block = list(self.blocks_dict.values())[dist_index]
                # print("new found: ", found_block, "from dist:", dist_index)
                collect_block = self.find_collect_block(found_block)
                # print(collect_block)
                if collect_block is not None:
                    # for d in self.just_dropped_off:
                    #     print(d)
                    # print(found_block not in self.just_dropped_off)
                    # print(self.find_claimed_block(collect_block) is None)
                    # print(self.block_is_one_step_right(found_block, collect_block) or not self.other_is_holding_block(collect_block))
                    # print(not self.block_is_dropped_off(found_block))
                    # print("objective", self.block_objective)
                    # for b in self.blocks_dict.values():
                    #     print("bdvalue:", b)
                    # print(self.block_objective is None)

                    if found_block not in self.just_dropped_off and \
                        self.find_claimed_block(collect_block) is None and \
                            (self.block_is_one_step_right(found_block, collect_block) or not self.other_is_holding_block(collect_block)) and \
                            not self.block_is_dropped_off(found_block) and \
                            self.block_objective is None:
                        self.block_objective = found_block
                        
                        self.blocks_dict.get(self.block_objective.get_obj_id()).set_carried_by([self.agent_id])
                        print("new objective", self.agent_id, self.block_objective)


                        locs = self.get_door_then_block_loc(state, objects, found_block)
                        self.update_waypoint(locs)
                        return True
            # self.block_objective = None
            return False

    def block_is_one_step_right(self, block, collect_block):
        block_loc = block.get_location()
        c_block_loc = collect_block.get_location()
        return (block_loc[0]-1, block_loc[1]) == c_block_loc


    def block_is_dropped_off(self, block):
        # print("block is dropped off")
        # print(block)
        retbool = False
        # for cblock in self.collect_blocks.values():
        #     if cblock.get_shape() == block.get_shape() and cblock.get_colour() == block.get_colour():
        #         retbool = False
        #         for bblock in self.blocks_dict.values():
        #             if bblock.get_location() == cblock.get_location() and bblock.get_shape() is cblock.get_shape() and bblock.get_colour() is cblock.get_colour():
        #                 retbool = True
        #                 break
        # return retbool

        for cblock in self.collect_blocks.values():
            if cblock.get_shape() == block.get_shape() and cblock.get_colour() == block.get_colour():
                retbool = False
                # print(cblock)
                # for b in self.collect_blocks_completed:
                    # print("completed:", b)
                if cblock in self.collect_blocks_completed:
                        retbool = True
                        break
        return retbool

    def find_holding_block(self, collect_block):
        for block in self.holding_blocks.values():
            if self.agent_id in block.get_carried_by():
                if collect_block.get_colour() is block.get_colour() and collect_block.get_shape() is block.get_shape():
                    return block
        return None

    def find_claimed_block(self, collect_block):
        for block in self.blocks_dict.values():
            if self.agent_id in block.get_carried_by():
                if collect_block.get_colour() is block.get_colour() and collect_block.get_shape() is block.get_shape():
                    return block
        return None

    def other_is_holding_block(self, collect_block):
        # print("other is holding block")
        for block in self.blocks_dict.values():
            if block.get_carried_by() and self.agent_id not in block.get_carried_by():

                if collect_block.get_colour() == block.get_colour() and collect_block.get_shape() == block.get_shape():
                    # print(block)
                    return True
        return False


    

    def open_nearby_doors(self, state):
        for doorId in self._nearbyDoors(state):
            if not state[doorId]['is_open']:
                return OpenDoorAction.__name__, {'object_id': doorId}
        return None

    def grab_block_and_go_to_first_drop_off_point(self, state):
        print("grabbing objective", self.agent_id, self.block_objective)
        action = self.grab_block(self.block_objective, state)
        return action

    def drop_block_and_go_to_next_drop_off_point(self, state):
        holding_block = self.find_holding_block(self.collect_block_objective)
        action = None

        # Placing holding_block to the right of the dropzone if holding_block is not the next block to be place
        one_step_right = (self.collect_block_objective.get_location()[0] + 1, self.collect_block_objective.get_location()[1])
        # print('here')
        # print(self.is_it_this_blocks_turn(holding_block))
        # print(self.state[self.agent_id]['location'] == one_step_right)
        # print('here2')
        if holding_block is not None and self.is_it_this_blocks_turn(holding_block):
            action = self.drop_block(holding_block, state)
            # if holding_block in self.blocks_set_beside_collect_block:
            #     self.blocks_set_beside_collect_block.pop(holding_block)
            # print("here")
            # print("new completed", self.find_collect_block(holding_block), holding_block)
            self.collect_blocks_completed.append(self.find_collect_block(holding_block))
            # Pop if we can drop the block
            self.holding_blocks.pop(holding_block.get_obj_id())
            # self.unclaim_blocks_not_objective_or_holding()
            self.collect_block_objective = self.get_first_collect_block()
            if self.collect_block_objective is not None:
                self.update_waypoint([self.collect_block_objective.get_location()])

        elif holding_block is not None and self.state[self.agent_id]['location'] == one_step_right:
            action = self.drop_block(holding_block, state)
            # print("here2")
            self.holding_blocks.pop(holding_block.get_obj_id())
            self.one_step_right_bool = False
            # self.blocks_set_beside_collect_block.append(holding_block)
            self.collect_block_objective = self.get_first_collect_block()
            if self.collect_block_objective is not None:
                self.update_waypoint([self.collect_block_objective.get_location()])
        else:
            # print("one step right", self.agent_id)
            action: tuple = (None, {})
            self.update_waypoint([one_step_right])
            self.one_step_right_bool = True


        return action

    def is_it_this_blocks_turn(self, block):
        # print("is_it_this_blocks_turn")
        c_block = self.find_collect_block(block)
        # print(c_block)
        for c_block_from_list in self.collect_blocks.values():
            # print(c_block_from_list)
            if c_block_from_list != c_block:
                # print("got here")
                if c_block_from_list not in self.collect_blocks_completed:
                    # print("returning false")
                    return False
            else:
                # print("returning true")
                return True

    def get_first_collect_block(self):
        for cblock in self.collect_blocks:
            collect_block = self.collect_blocks[cblock]
            if self.find_holding_block(collect_block) is not None:
                return collect_block
        return None

    def update_waypoint(self, locations):
        self.navigator.reset_full()
        self.navigator.add_waypoints(locations)

    def get_action(self, state):
        self.state_tracker.update(state)
        action = self.navigator.get_move_action(self.state_tracker)

        return action

    def get_door_then_block_loc(self, state, objects, obj_block):
        block_split = obj_block.get_obj_id().split("_")
        roomnr = block_split[2] + "_" + block_split[3]
        blocks = [state[obj] for obj in objects if roomnr + "_-_door" in obj]
        block = blocks[0]
        door = block.get('location')
        loc1 = (door[0], door[1] + 1)
        loc2 = obj_block.get_location()
        if block.get("is_open"):
            return [loc2]
        else:
            return [loc1, loc2]

    def get_collect_blocks(self, state, objects):
        if len(self.collect_blocks) == 0:
            blocks = [state[obj] for obj in objects if "Collect_Block" in obj]
            for block in blocks:
                obj_id = block.get('obj_id')
                carried_by = []
                location = block.get('location')
                color = block.get('visualization', {}).get('colour')
                shape = block.get('visualization', {}).get('shape')
                newBlock = Block(obj_id, location, carried_by, color, shape)
                self.collect_blocks.update({obj_id: newBlock})

    def update_block_dict(self, state, objects):
        blocks = [state[obj] for obj in objects if "Block_in_room" in obj]
        for block in blocks:
            obj_id = block.get('obj_id')
            carried_by = []
            location = block.get('location')
            color = block.get('visualization', {}).get('colour')
            shape = block.get('visualization', {}).get('shape')
            newBlock = Block(obj_id, location, carried_by, color, shape)
            if self.blocks_dict.get(obj_id) is None:
                self.blocks_dict.update({obj_id: newBlock})
            else:
                self.blocks_dict.update({obj_id: newBlock + self.blocks_dict[obj_id]})

    def grab_block(self, block, state):
        self.holding_blocks.update({block.get_obj_id(): block})
        self.block_objective = None
        return GrabObject.__name__, {'object_id': block.get_obj_id()}

    def drop_block(self, block, state):
        self.blocks_dict.get(block.get_obj_id()).set_carried_by([])
        self.blocks_dict.get(block.get_obj_id()).set_location(state[self.agent_id]['location'])
        print("dropping block: ", self.blocks_dict.get(block.get_obj_id()), self.agent_id)

        self.just_dropped_off.append(self.blocks_dict.get(block.get_obj_id()))

        # msg = self.dict_to_str_block(self.blocks_dict.get(block.get_obj_id()))
        # self.msgQueue.append(msg)
        # self.block_sent_list.update({block.get_obj_id(): block})
        return DropObject.__name__, {'object_id': block.get_obj_id()}

    def _nearbyDoors(self, state: State):
        # copy from humanagent
        # Get all doors from the perceived objects
        objects = list(state.keys())
        doors = [obj for obj in objects if 'is_open' in state[obj]]
        doors_in_range = []
        for object_id in doors:
            # Select range as just enough to grab that object
            dist = int(np.ceil(np.linalg.norm(
                np.array(state[object_id]['location']) - np.array(
                    state[self.agent_id]['location']))))
            if dist <= self._door_range:
                doors_in_range.append(object_id)
        return doors_in_range

    def find_collect_block(self, fblock):
        for collect_block in self.collect_blocks.values():
            if collect_block.get_colour() == fblock.get_colour() and collect_block.get_shape() == fblock.get_shape():
                return collect_block
        return None

    @staticmethod
    def dict_to_str_block(block: Block):
        """
        Format: { '<obj_id>' : {
            '<obj_id>':...,
            '<location':...,
            '<carried_by>':...,
            '<colour>':...,
            '<shape>':...
        }}
        :param block: the block dict to convert to a str
        :param agent_id: the id of the agent carrying the block, None if no agent carries the block
        :return: string representation with expected format of the given block dict object
        """
        block_msg = FORMAT_BLOCK_MSG_SEND.format(repr(block.get_obj_id()),
                                                 block.get_location(),
                                                 block.get_carried_by(),
                                                 repr(block.get_colour()),
                                                 block.get_shape())
        return block_msg

    @staticmethod
    def choose_room(state):
        # Get all room door objects.
        rooms_doors = [door for room in state.get_all_room_names() if 'room' in room for door in state.get_room_doors(room)]
        # Check for all closed doors and get the indices.
        rooms_closed = [idx for idx,door in enumerate(rooms_doors) if not door['is_open']]
        # Choose random door from closed doors list and if there is none choose door from all rooms.
        room_to_go = rooms_doors[random.choice(rooms_closed)] if rooms_closed else random.choice(rooms_doors)

        door = room_to_go.get('location')
        loc = (door[0], door[1]+1)
        return [loc]
