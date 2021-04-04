from typing import List, Dict, Tuple
import numpy as np  # type: ignore
from matrx.actions import MoveNorth, OpenDoorAction, CloseDoorAction, GrabObject, DropObject  # type: ignore
from matrx.actions.move_actions import MoveEast, MoveSouth, MoveWest  # type: ignore
from matrx.agents.agent_utils.state import State  # type: ignore

from bw4t.BW4TBrain import BW4TBrain
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state_tracker import StateTracker

from matrx.messages import Message

import random
import ast

from typing import Dict
import ast


class Block:
    def __init__(self,
                 obj_id: str,
                 location: tuple,
                 colour: str,
                 shape: int,
                 **kwargs):
        """
        Constructor for a block object
        :param obj_id: object id of the block
        :param location: location of the block
        :param colour: colour of the block
        :param shape: shape of the block
        :param kwargs: other fields that are not important to store
        """
        self.obj_id = obj_id
        self.location = location
        self.carried_by = []
        self.check_required_fields()
        self.colour = colour
        self.shape = shape

    def __str__(self):
        """
        String representation of this block
        :return: String representation of this block
        """
        return "{{" \
               "'obj_id': {0}," \
               "'location': {1}," \
               "'colour': {2}," \
               "'shape': {3}, " \
               "'carried_by': {4}" \
               "}}" \
            .format(repr(self.obj_id),
                    self.location,
                    repr(self.colour) if self.colour else None,
                    self.shape,
                    self.carried_by)

    def __copy__(self):
        """
        Copy method for this block
        :return: new Block object with same data as this block
        """
        return Block(self.obj_id, self.location, self.colour, self.shape)

    def __add__(self, other):
        """
        Merges the self block with the other block.
        Always defaults to the values contained in the self block if other block
        does not contain info the we expect (colour and shape info).
        NOTE: other must be of type Block!
        :param other: block to merge with self (this) block
        :return: new Block object containing the merged values for colour and shape as defined in description
                and retains the values for obj_id, location and carried_by
        """
        if self.get_obj_id() != other.get_obj_id():

            print(
                "VALUE ERROR: " + self.__str__() + " AND " + other.__str__() + " DOESN'T HAVE EQUAL NECESSARY FIELD "
                                                                               "VALUES!")
            return None

        else:
            block_ret = Block(self.obj_id, other.get_location(), None, None)
            block_ret.set_carried_by(other.get_carried_by())
            if other.get_colour() is not None and self.get_colour() is None:
                block_ret.set_colour(other.get_colour())
            else:
                block_ret.set_colour(self.get_colour())
            if other.get_shape() is not None and self.get_shape() is None:
                block_ret.set_shape(other.get_shape())
            else:
                block_ret.set_shape(self.get_shape())
            return block_ret

    def __eq__(self, other):
        """
        Checks equality between 2 blocks
        :param other: the other Block object
        :return: True if the this and other blocks are equal, otherwise False
        """
        if not isinstance(other, Block):
            # don't attempt to compare against unrelated types
            print("ERROR COMPARISON BLOCK: ", other, " IS NOT A BLOCK INSTANCE!")
            return False

        return self.obj_id == other.obj_id and \
               self.location == other.location and \
               self.carried_by == other.carried_by and \
               self.colour == other.colour and \
               self.shape == other.shape

    def __hash__(self):
        """
        Hash this block object
        :return: Hash of this block object
        """
        return hash((self.obj_id, self.location, self.colour, self.shape))

    def check_required_fields(self):
        """
        Checks the required fields that every block must have
        :return: None if this block has the required fields, otherwise ValueError
        """
        obj_id_check = self.obj_id is not None and isinstance(self.obj_id, str)
        location_check = self.location is not None and isinstance(self.location, tuple) and \
                         isinstance(self.location[0], int) and isinstance(self.location[1], int)
        if obj_id_check and location_check:
            return
        else:
            raise ValueError("UNEXPECTED VALUES FOR BLOCK CREATION: "
                             f"self.obj_id = {self.obj_id}"
                             f"self.location = {self.location}"
                             f"self.carried_by = {self.carried_by}")

    def get_colour(self) -> str:
        """
        Getter method for colour of this block
        :return: Colour of this block
        """
        return self.colour

    def get_shape(self) -> int:
        """
        Getter method for shape of this block
        :return: Shape of this block
        """
        return self.shape

    def get_location(self):
        """
        Getter method for location of this block
        :return: Location of this block
        """
        return self.location

    def get_obj_id(self):
        """
        Getter method for object id of this block
        :return: Object id of this block
        """
        return self.obj_id

    def get_carried_by(self):
        """
        Getter method for carried_by of this block
        :return: Carried_by list of this block
        """
        return self.carried_by

    def set_location(self, loc):
        """
        Setter method for location of this block
        :param loc: new location
        :return: None
        """
        self.location = loc

    def set_carried_by(self, val):
        """
        Setter for carried_by list
        :param val: new carried_by list
        :return: None
        """
        self.carried_by = val

    def set_colour(self, val):
        """
        Setter for colour
        :param val: new colour value
        :return: None
        """
        self.colour = val

    def set_shape(self, val):
        """
        Setter for shape
        :param val: new shape value
        :return: None
        """
        self.shape = val


class Team19Agent(BW4TBrain):
    """
    This is Team 19's agent
    """

    def __init__(self, settings: Dict[str, object]):
        super().__init__(settings)
        self.handicaps = self.get_handicap(settings)
        self._moves = [MoveNorth.__name__, MoveEast.__name__, MoveSouth.__name__, MoveWest.__name__]

    def initialize(self):
        super().initialize()
        self._door_range = 1
        self.state_tracker = StateTracker(agent_id=self.agent_id)
        self.navigator = Navigator(agent_id=self.agent_id, action_set=self.action_set,
                                   algorithm=Navigator.A_STAR_ALGORITHM)

        self.firstTick = True
        self.skipTick = False
        self.last_tile_circle = None

        self.block_objective = None
        self.collect_block_objective = None
        self.collect_blocks: Dict[str, Block] = {}
        self.picked_up_collect_blocks: List[str] = []
        self.my_picked_up_collect_blocks: List[Block] = []
        self.occupied_rooms: Dict[str, str] = {}
        self.blocks_dict: Dict[str, Block] = {}
        self.block_sent_list: Dict[str, tuple] = {}
        self.just_dropped_off = []
        self.duplicates_dropped = []
        self.cb_iterator = None
        self.checking_disabled_room = False

    def filter_bw4t_observations(self, state):
        """
        Handles incoming messages, checks state object and decides on a new objective.
        :return: None
        """
        objects = list(state.keys())

        if self.firstTick:
            loc = self.choose_room(state)
            self.update_waypoint(loc)

            self.firstTick = False
            self.get_collect_blocks(state, objects)

            # convert collect blocks in expected format and send desired blocks
            self.send_desired_blocks()

        self.update_block_dict(state, objects)

        for msg in self.received_messages:
            if isinstance(msg, dict):
                msg_dict_general = msg
                msglower = msg
            else:
                msg_dict_general = ast.literal_eval(msg)
                msglower = msg.lower()

            # handle update map
            if 'update_map' in msglower:
                self.handle_update_map(msg_dict_general)

            # handle update room
            elif 'room_name' in msglower:
                self.handle_update_room(state, msg_dict_general)

            # handle desired block update (collect blocks)
            elif 'desired_blocks' in msglower:
                self.handle_desired_block_update(msg_dict_general)

            # handle picked up block by another agent
            elif 'picked_up_block' in msglower:
                self.handle_picked_up_block(msg_dict_general)

        self.send_update_map()

        if self.last_tile_circle and state[self.agent_id]['location'] == self.last_tile_circle:
            self.last_tile_circle = None
            if self.checking_disabled_room:
                self.send_finish_disabled_door()
                self.checking_disabled_room = False
            else:
                self.send_disabled_door()

        if not self.last_tile_circle:
            # if no objective (meaning you're not on your way to a block right now), check if all blocks of interest have been claimed
            # (meaning they've either been picked up or an agent is planning to pick it up)
            if self.block_objective is None and \
                    self.collect_block_objective is None and \
                    self.all_blocks_of_interest_claimed():

                # go to the next drop off zone in the iterator
                self.collect_block_objective = self.get_next_collect_block()
                if self.collect_block_objective is not None:
                    self.update_waypoint([self.collect_block_objective.get_location()])

            elif not self.all_blocks_of_interest_claimed():  # If not all blocks of interest have been claimed go look for a new block of interest
                self.check_for_block_of_interest_and_go_to_it(state, objects)

            # if no objective, check if there's block information missing which you can add to
            if self.block_objective is None and self.collect_block_objective is None:
                block_with_none_loc = self.get_location_of_blocks_with_none(state, objects)
                if block_with_none_loc:
                    self.update_waypoint(block_with_none_loc)

        # empty received messages (because of this bug: https://github.com/matrx-software/matrx/issues/240)
        self.received_messages = []
        return state

    def decide_on_bw4t_action(self, state: State):
        """
        Decide on action to perform.
        :return: action
        """
        action = self.open_nearby_doors(state)
        if action is not None: # If there's a door nearby to be opened, do that.
            return action

        action = self.get_action(state)
        if action is None and self.block_objective is not None:
            action = self.grab_block_and_go_to_first_drop_off_point()
        elif action is None and self.collect_block_objective is not None:
            action = self.drop_block_and_go_to_next_drop_off_point(state)
        elif action is None: #If there's nothing to do, choose a room and go find new blocks
            loc = self.choose_room(state)
            self.update_waypoint(loc)
            action: tuple = (action, {})
        else:
            action: tuple = (action, {})

        return action

    def send_desired_blocks(self):
        """
        Send information about the collect blocks that the agent knows of to other agents.
        This is done in the required format that other agents expect.
        :return: None
        """
        list_of_desired_blocks = []
        for b in self.collect_blocks.values():
            if b.get_colour() is None and b.get_shape() is None:
                collect_b_dict = {b.get_obj_id(): {}}
            elif b.get_colour() is None:
                collect_b_dict = {b.get_obj_id(): {'shape': b.get_shape()}}
            elif b.get_shape() is None:
                collect_b_dict = {b.get_obj_id(): {'colour': b.get_colour()}}
            else:
                collect_b_dict = {b.get_obj_id(): {'colour': b.get_colour(), 'shape': b.get_shape()}}
            list_of_desired_blocks.append(collect_b_dict)

        format_msg = "{{ 'agent_id': {0} , 'desired_blocks': {1} }}".format(repr(self.agent_id), list_of_desired_blocks)
        self.send_message(Message(content=format_msg, from_id=self.agent_id))

    def send_update_map(self):
        """
        Send message with required information about the blocks in the vicinity of the agent to other agents.
        This is done in the required format that other agents expect.
        :return: None
        """
        list_of_msgs_to_send: List[Tuple] = []

        for block in self.blocks_dict.values():
            # add to list to keep track of what has already been sent
            b_to_append = (block.get_location(),
                            {'obj_id': block.get_obj_id(), 'colour': block.get_colour(), 'shape': block.get_shape()})

            if b_to_append not in self.block_sent_list.values():
                list_of_msgs_to_send.append(b_to_append)
                self.block_sent_list.update({block.get_obj_id(): b_to_append})

        if list_of_msgs_to_send:
            # convert to msg string format
            msg = f"{{'agent_id': {repr(self.agent_id)}, 'update_map': {list_of_msgs_to_send} }}"
            self.send_message(Message(content=msg, from_id=self.agent_id))

    def send_picked_up_block(self, picked_up_block: Block, collect_block_id):
        """
        Send the picked up block by the agent to other agents in the required format.
        :param picked_up_block: The block that has been picked up.
        :param collect_block_id: Collect block obj_id that corresponds to the picked up block.
        :return: None
        """
        obj_to_send = {'goal_block_id': collect_block_id,
                       'picked_up_block_id': picked_up_block.get_obj_id(),
                       'colour': picked_up_block.get_colour(),
                       'shape': picked_up_block.get_shape()}
        msg = f"{{'agent_id': {repr(self.agent_id)}, 'picked_up_block': {obj_to_send} }}"
        self.send_message(Message(content=msg, from_id=self.agent_id))

    def send_disabled_door(self):
        """
        Send message about the room that has been visited by the agent (if agent has handicap)
        to other agents for other agents to revisit this door (as not all info about the blocks is known in this case).
        :return: None
        """
        if self.handicaps:
            handicaps = {}
            if 'colorblind' in self.handicaps and 'shapeblind' in self.handicaps:
                handicaps = {'colour': True, 'shape': True}
            if 'colorblind' in self.handicaps:
                handicaps = { 'colour': True}
            if 'shapeblind' in self.handicaps:
                handicaps = {'shape': True}
            inner_msg = {self.door_id_of_checked_room: handicaps}
            msg = f"{{'agent_id': {repr(self.agent_id)}, 'disabled_door': {inner_msg} }}"
            self.send_message(Message(content=msg, from_id=self.agent_id))

    def send_finish_disabled_door(self):
        """
        Send message about the fact that the room has been visited and all info about the blocks in the room are known.
        :return: None
        """
        inner_msg = {'door_id': self.door_id_of_checked_room}
        msg = f"{{'agent_id': {repr(self.agent_id)}, 'finish_disabled_door': {inner_msg} }}"
        self.send_message(Message(content=msg, from_id=self.agent_id))


    def handle_picked_up_block(self, msg_dict: dict):
        """
        Handler for the logic that needs to be done for when other agents sent a message that they picked up a block.
        :param msg_dict: the message dictionary to read the required info from
        :return: None
        """
        # fetch necessary info
        agent_id = msg_dict['agent_id']
        picked_block_obj = msg_dict['picked_up_block']
        picked_block_goal_id = picked_block_obj['goal_block_id']
        picked_block_obj_id = picked_block_obj['picked_up_block_id']

        # update the carried_by field of the picked up block
        update_block_carried_by = self.blocks_dict.get(picked_block_obj_id)
        
        carried_by = update_block_carried_by.get_carried_by()
        if carried_by:
            if agent_id < carried_by[0]:
                update_block_carried_by.set_carried_by([agent_id])
        else:
            update_block_carried_by.set_carried_by([agent_id])

        update_block_carried_by.set_carried_by([agent_id])
        self.blocks_dict.update({picked_block_obj_id: update_block_carried_by})

        if self.block_objective is not None and self.agent_id not in self.blocks_dict.get(
                self.block_objective.get_obj_id()).get_carried_by():
            self.block_objective = None

        # keep track of collect block ids to not pick up the same block that corresponds to this collect block
        self.picked_up_collect_blocks.append(picked_block_goal_id)

    def handle_update_map(self, msg_dict: dict):
        """
        Handle the logic of the update message from other agents.
        This updates the blocks_dict list.
        :param msg_dict: the message dictionary to read the required info from
        :return: None
        """
        list_blocks_tuples = msg_dict['update_map']
        for tup in list_blocks_tuples:
            location_block = tup[0]
            obj_block = tup[1]
            if obj_block is not False and obj_block is not None:
                obj_id = obj_block['obj_id']
                obj_colour = obj_block.get('colour')
                obj_shape = obj_block.get('shape')
                rec_block = Block(obj_id=obj_id, location=location_block,
                          colour=obj_colour, shape=obj_shape)

                block_in_list = self.blocks_dict.get(obj_id)
                if block_in_list is None:
                    self.blocks_dict.update({obj_id: rec_block})
                else:
                    newBlock = rec_block + self.blocks_dict[obj_id]
                    self.blocks_dict.update({obj_id: newBlock})

                r_block = self.blocks_dict.get(obj_id)
                b_message = (r_block.get_location(),
                            {'obj_id': r_block.get_obj_id(), 'colour': r_block.get_colour(), 'shape': r_block.get_shape()})
                self.block_sent_list.update({obj_id: b_message})

    def handle_desired_block_update(self, msg_dict: dict):
        """
        Handle the logic of the update collect block message from other agents.
        This updates the collect_blocks list.
        :param msg_dict: the message dictionary to read the required info from
        :return: None
        """
        # Only update collect block if colour or shape is missing
        collect_blocks = msg_dict['desired_blocks']
        for cb in collect_blocks:
            cb_obj_id, cb_colour_shape = list(cb.items())[0]
            cb_colour = cb_colour_shape.get('colour')
            cb_shape = cb_colour_shape.get('shape')
            our_own_cb = self.collect_blocks[cb_obj_id]
            if cb_colour is not None and our_own_cb.get_colour() is None:
                our_own_cb.set_colour(cb_colour)
            if cb_shape is not None and our_own_cb.get_shape() is None:
                our_own_cb.set_shape(cb_shape)
            self.collect_blocks.update({cb_obj_id: our_own_cb})

    def handle_update_room(self, state: State, msg_dict: dict):
        """
        Update the room to contain the agent id of the agent that is currently present in the room.
        Current agent would choose another room if the agent of the message has the same room and lower agent id.
        :param msg_dict: the message dictionary to read the required info from
        :return: None
        """
        msg_room_name = msg_dict['room_name']
        msg_agent_id = msg_dict['agent_id']

        # we don't have to check out messages as we already know it
        # so only check messages of other agents
        if msg_agent_id != self.agent_id:
            # check if the sending agent want to go to the same room
            # as the room that we want to go to
            if self.occupied_rooms[self.agent_id] == msg_room_name:
                # if sending agent has lower id, then we have to choose another
                # room to visit, as lowest agent id has more priority
                if self.agent_id > msg_agent_id:
                    # Update occupied room so the other agent goes to that room
                    self.occupied_rooms[msg_agent_id] = msg_room_name
                    # Choose random room now that our agent can't go to that
                    loc = self.choose_room(state)
                    self.update_waypoint(loc)
            else:
                # Since this doesn't concern our room,
                # just update the occupied room with latest information
                self.occupied_rooms[msg_agent_id] = msg_room_name

    def all_blocks_of_interest_claimed(self):
        """
        Checks whether the agent has collected/claimed all the collect blocks.
        :return: True if all the collect blocks are claimed, otherwise False.
        """
        for cblock in self.collect_blocks.values():
            if not self.block_is_claimed(cblock, self.collect_blocks.values()):
                return False
        return True

    def get_location_of_blocks_with_none(self, state: State, objects):
        """
        Get location of all blocks that either have colour as none or shape as none
        depending on the handicap of the agent
        :return: list of location/waypoints for the agent to visit to check
         what colour or shape the blocks have
        """
        blocks_to_check = []
        if self.handicaps:
            if not ("colorblind" in self.handicaps and "shapeblind" in self.handicaps):
                if "colorblind" in self.handicaps:
                    blocks_to_check = [b for b in self.blocks_dict.values() if b.get_shape() is None]
                elif "shapeblind" in self.handicaps:
                    blocks_to_check = [b for b in self.blocks_dict.values() if b.get_colour() is None]
        else:
            blocks_to_check = [b for b in self.blocks_dict.values() if b.get_shape() is None
                               or b.get_colour() is None]
        if blocks_to_check:
            dist_to_blocks = [self.dist_agent_to_block(state, b) for b in blocks_to_check]
            closest_block_idx = dist_to_blocks.index(min(dist_to_blocks))
            closest_block = blocks_to_check[closest_block_idx]


            door = self.get_door(state, objects, closest_block)
            door_loc = door.get('location')
            door_id = door.get('obj_id')
            tile_locs = self.make_circle_in_room(state, door.get('room_name'))
            tile_locs.insert(0, door_loc)

            self.last_tile_circle = tile_locs[-1]
            self.door_id_of_checked_room = door_id
            self.checking_disabled_room = True

            return tile_locs

        return blocks_to_check

    def dist_agent_to_block(self, state: State, block: Block):
        """
        Norm distance (Eucledian distance) from agent to given block
        :param state: to get agent current location in the current state
        :param block: the block to which to calculate the distance to
        :return: distance from agent to given block
        """
        return np.linalg.norm(
                np.array(block.get_location()) - np.array(
                    state[self.agent_id]['location']))

    def make_circle_in_room(self, state: State, room_name: str):
        """
        Returns coordinates of the room tiles for the agent to make a circle in the visited room.
        :param state: current state object
        :param room_name: the room name that is visited by the agent
        :return: List of coordinates of room tiles
        """
        room_area_objs = state.get_room_objects(room_name)

        # get all coordinates of tiles of the given room
        locations_room: list = []
        for room_dict in room_area_objs:
            locations_room.append(room_dict['location'])

        return [locations_room[1], locations_room[0], locations_room[-2], locations_room[-1]]

    def get_distance_to_blocks(self, state: State):
        """
        Calculates the distance of the agent to all the blocks known until now
        and return list of distances sorted from small to large distances
        :param state: state object to fetch agents location from
        :return: list of distances sorted from small to large distances
        """
        dist_to_blocks = []

        # for each seen block, calculate dist of agent to the block
        for block in self.blocks_dict.values():
            curr_block_dist = self.dist_agent_to_block(state, block)
            dist_to_blocks.append(curr_block_dist)

        return dist_to_blocks


    def get_next_collect_block(self):
        """
        Get the next collect block in the collect block iterator.
        If no iterator exists yet, create one
        Returns None if all collect blocks have been iterated over.
        :return: The next collect block to collect.
        """
        self.my_picked_up_collect_blocks.sort(key=lambda x: x.get_obj_id())
        try:
            if self.cb_iterator == None:
                self.cb_iterator = iter(self.my_picked_up_collect_blocks)
            next_cb = next(self.cb_iterator)
            return next_cb
        except StopIteration:
            return None

    def block_is_claimed(self, collect_block, collect_blocks):
        """
        Checks whether the given collect block is claimed or not.
        :param collect_block: collect block to check.
        :param collect_blocks: list of known collect blocks.
        :return: True if collect block is claimed, otherwise False.
        """
        cb_index = self.same_collect_block_before_count(collect_block, collect_blocks)
        count = 0
        for block in self.blocks_dict.values():
            if block.get_carried_by():
                if collect_block.get_colour() == block.get_colour() and collect_block.get_shape() is block.get_shape():
                    if count == cb_index:
                        return True
                    else:
                        count = count + 1
        return False

    def check_for_block_of_interest_and_go_to_it(self, state, objects):
        """
        Checks what the closest block is that the agent can go to and claim.
        :param state: state object.
        :param objects: keys of state object.
        :return: True if an objective block has been assigned to the agent, otherwise False.
        """
        if self.blocks_dict:
            distance_list = self.get_distance_to_blocks(state)
            distance_list_sorted_indexes = sorted(range(len(distance_list)), key=lambda k: distance_list[k])
            for dist_index in distance_list_sorted_indexes:
                found_block = list(self.blocks_dict.values())[dist_index]

                if found_block.get_shape() is None or found_block.get_colour() is None:
                    continue

                collect_blocks_list = self.find_collect_blocks(found_block)
                for collect_block in collect_blocks_list:
                    if not found_block.get_carried_by() and \
                            not self.block_is_claimed(collect_block, self.collect_blocks.values()) and \
                            self.block_objective is None:

                        found_block.set_carried_by([self.agent_id])

                        self.block_objective = found_block
                        self.blocks_dict.update({found_block.get_obj_id(): found_block})

                        # send to other agents that the block is claimed
                        self.send_picked_up_block(found_block, collect_block.get_obj_id())
                        self.my_picked_up_collect_blocks.append(collect_block)

                        locs = self.get_door_then_block_loc(state, objects, found_block)
                        self.update_waypoint(locs)
                        return True

            return False

    @staticmethod
    def block_is_one_step_right(block, collect_block):
        """
        Checks if the given block is right to its collect block.
        :param block: the block to check.
        :param collect_block: collect block of the given block.
        :return: True if block is right to its collect block, otherwise False.
        """
        block_loc = block.get_location()
        c_block_loc = collect_block.get_location()
        return (block_loc[0]-1, block_loc[1]) == c_block_loc

    def find_holding_block(self, state, collect_block):
        """
        Checks whether a block that corresponds to the given collect block is currently held by the agent.
        :param state: state object.
        :param collect_block: collect block to check.
        :return: Block that is held by the agent that corresponds to the given collect block, otherwise None.
        """
        for block in state[self.agent_id]['is_carrying']:
            if block.get('obj_id') in self.just_dropped_off:  # needed because state doesn't directly update when dropped a block
                continue
            dict_block = self.blocks_dict.get(block.get('obj_id'))
            if collect_block.get_colour() == dict_block.get_colour() and \
                    collect_block.get_shape() is dict_block.get_shape():
                return dict_block
        return None

    def find_claimed_block(self, collect_block):
        """
        Checks whether a block that corresponds to the given collect block is currently claimed by the agent.
        :param collect_block: collect block to check.
        :return: Block that is claimed by the agent that corresponds to the given collect block, otherwise None.
        """
        for block in self.blocks_dict.values():
            if self.agent_id in block.get_carried_by():
                if collect_block.get_colour() is block.get_colour() and collect_block.get_shape() is block.get_shape():
                    return block
        return None

    def other_is_holding_block(self, collect_block):
        """
        Checks if a block of same colour and shape as given collect block is carried by other agents.
        :param collect_block:
        :return: True if there is an agent that is already holding a block of same
        colour and shape as the given collect block, otherwise False.
        """
        for block in self.blocks_dict.values():
            if block.get_carried_by() and self.agent_id not in block.get_carried_by():
                if collect_block.get_colour() == block.get_colour() and collect_block.get_shape() == block.get_shape():
                    return True
        return False

    def open_nearby_doors(self, state):
        """
        Opens nearby door
        :param state: state object
        :return: action of opening a door.
        """
        for doorId in self._nearbyDoors(state):
            if not state[doorId]['is_open']:
                return OpenDoorAction.__name__, {'object_id': doorId}
        return None

    def grab_block_and_go_to_first_drop_off_point(self):
        """
        Commands an agent to grab the objective block.
        :return: action of grabbing the objective block to be executed by the agent.
        """
        action = self.grab_block(self.block_objective)
        return action

    def drop_block_and_go_to_next_drop_off_point(self, state):
        """
        Drops objective block in the proper collect block drop off zone in the right order.
        :param state: state object.
        :return: action of dropping or None.
        """
        holding_block = self.find_holding_block(state, self.collect_block_objective)
        action = None

        if self.block_already_dropped_here(state):
            self.collect_block_objective = None
            return (None, {})

        if holding_block is not None and self.is_it_this_blocks_turn(state):
            action = self.drop_block(holding_block, state)
            self.collect_block_objective = None
        else:
            action: tuple = (None, {})

        return action

    def is_it_this_blocks_turn(self, state):
        """
        Check if it is this block's turn to be placed.
        :param state: state object.
        :return: True if it is this block's turn to be placed, otherwise False.
        """
        my_loc = state[self.agent_id]['location']
        collect_block_keys = list(self.collect_blocks.keys())
        if my_loc == self.collect_blocks.get(collect_block_keys[0]).get_location():
            return True

        tile_below_me = (my_loc[0], my_loc[1] + 1)

        objects = list(state.keys())
        blocks_around = [state[obj] for obj in objects if 'Block_in_room' in obj]
        for block in blocks_around:
            if block.get('location') == tile_below_me:
                return True

        return False

    def block_already_dropped_here(self, state):
        """
        Check if there is already a block dropped in the location of the agent.
        :param state: state object.
        :return: True if there is already a block dropped in the location of the agent, otherwise False.
        """
        my_loc = state[self.agent_id]['location']
        objects = list(state.keys())
        blocks_around = [state[obj] for obj in objects if 'Block_in_room' in obj]
        for block in blocks_around:
            if block.get('location') == my_loc:
                return True
        return False

    def update_waypoint(self, locations):
        """
        Update waypoint of the agent to the given locations.
        :param locations: locations that the agent needs to go to.
        :return: None
        """
        self.navigator.reset_full()
        self.navigator.add_waypoints(locations)

    def get_action(self, state):
        """
        Fetches current action of the agent.
        :param state: state object.
        :return: current action of agent
        """
        self.state_tracker.update(state)
        action = self.navigator.get_move_action(self.state_tracker)
        return action

    def get_door_then_block_loc(self, state, objects, obj_block):
        """
        Fetch location to the block and its corresponding door if door is closed,
        otherwise fetch location to block only.
        :param state: state object.
        :param objects: keys of state object.
        :param obj_block: objective block
        :return: locations to the door and to the block if door is closed, otherwise location to the block.
        """
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

    @staticmethod
    def get_door(state, objects, obj_block):
        """
        Get door of the room of the objective block.
        :param state: state object.
        :param objects: keys of state object.
        :param obj_block: objective block.
        :return: The door of the objective block.
        """
        block_split = obj_block.get_obj_id().split("_")
        roomnr = block_split[2] + "_" + block_split[3]
        blocks = [state[obj] for obj in objects if roomnr + "_-_door" in obj]
        block = blocks[0]
        return block

    def get_collect_blocks(self, state, objects):
        """
        Updates dict of collect blocks to contain the collect blocks that the agent knows of.
        :param state: state object.
        :param objects: keys of state object.
        :return: None
        """
        if len(self.collect_blocks) == 0:
            blocks = [state[obj] for obj in objects if "Collect_Block" in obj]
            for block_dict in blocks:
                obj_id = block_dict['obj_id']
                colour = block_dict.get('visualization').get('colour')
                shape = block_dict.get('visualization').get('shape')
                location = block_dict['location']
                newBlock = Block(obj_id=obj_id, colour=colour, shape=shape, location=location)
                self.collect_blocks.update({obj_id: newBlock})

    def update_block_dict(self, state, objects):
        """
        Updates dict of blocks to contain the blocks that the agent knows of.
        :param state: state object.
        :param objects: keys of state object.
        :return: None
        """
        blocks = [state[obj] for obj in objects if "Block_in_room" in obj]
        for block_dict in blocks:
            obj_id = block_dict['obj_id']
            colour = block_dict.get('visualization').get('colour')
            shape = block_dict.get('visualization').get('shape')
            location = block_dict['location']
            newBlock = Block(obj_id=obj_id, colour=colour, shape=shape, location=location)
            if self.blocks_dict.get(obj_id) is None:
                self.blocks_dict.update({obj_id: newBlock})
            else:
                self.blocks_dict.update({obj_id: newBlock + self.blocks_dict[obj_id]})

    def grab_block(self, block):
        """
        Grab action for a given block.
        :param block: block to grab.
        :return: action for grabbing the given block.
        """
        self.block_objective = None
        return GrabObject.__name__, {'object_id': block.get_obj_id()}

    def drop_block(self, block, state):
        """
        Drop action of a given block.
        :param block: block to drop.
        :param state: state object.
        :return: action for dropping the given block.
        """
        self.blocks_dict.get(block.get_obj_id()).set_location(state[self.agent_id]['location'])
        self.just_dropped_off.append(block.get_obj_id())
        return DropObject.__name__, {'object_id': block.get_obj_id()}

    def _nearbyDoors(self, state: State):
        """
        Fetches the doors in range of the agent.
        :param state: state object.
        :return: list of doors in range.
        """
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

    def find_collect_blocks(self, fblock):
        """
        Fetches blocks of which the corresponding collect block is not yet picked up by other agents.
        :param fblock: the block to search with.
        :return: List of collect blocks that can be picked up by the agent.
        """
        collect_blocks_list = []
        for collect_block in self.collect_blocks.values():
            if collect_block.get_colour() == fblock.get_colour() and collect_block.get_shape() == fblock.get_shape() and \
                collect_block.get_obj_id() not in self.picked_up_collect_blocks:
                collect_blocks_list.append(collect_block)
        return collect_blocks_list

    def choose_room(self, state):
        """
        The closest room with closed door is chosen for the agent to attend and to make circle motion in the room.
        Otherwise, if all rooms are opened,
        a random room is chosen for the agent to visit and to make a circle motion in the room.
        :param state: state object.
        :return: list of waypoints to the door and room tiles for the agent to attend to.
        """
        # Check for rooms that are already occupied by other agents
        rooms_occupied_list = self.occupied_rooms.values()
        rooms_not_occupied = [r for r in state.get_all_room_names()
                              if r not in rooms_occupied_list]
        # Get all room door objects.
        rooms_doors = [door for room in rooms_not_occupied if 'room' in room for door in state.get_room_doors(room)]
        # Check for all closed doors and get the indices.
        rooms_closed = [idx for idx, door in enumerate(rooms_doors) if not door['is_open']]
        # Choose random door from closed doors list and if there is none choose door from all rooms.
        room_to_go = rooms_doors[random.choice(rooms_closed)] if rooms_closed else random.choice(rooms_doors)

        door = room_to_go.get('location')
        door_id = room_to_go.get('obj_id')
        door_loc = (door[0], door[1]+1)

        tile_locs = self.make_circle_in_room(state, room_to_go.get('room_name'))
        tile_locs.insert(0, door_loc)
        self.last_tile_circle = tile_locs[-1]
        self.door_id_of_checked_room = door_id

        self.send_choose_room(room_to_go.get('room_name'))

        return tile_locs

    def send_choose_room(self, room_name):
        """
        Sends room that the agent want to go to other agents in the right format.
        :param room_name: the room name of the room that the agents want to go to.
        :return: None
        """
        # update to which room the agent go to
        self.occupied_rooms[self.agent_id] = room_name
        # send where the agent is going to all other agents
        msg = f"{{'agent_id': {repr(self.agent_id)}, 'room_name': {repr(room_name)}}}"
        self.send_message(Message(content=msg, from_id=self.agent_id))

    @staticmethod
    def get_handicap(settings: Dict[str, object]):
        """
        Fetches all handicaps that agent has, if any.
        :param settings: contains handicaps
        :return:
            [] if agent has no handicaps,
            ['colorblind'] if agent is only color blind or
            ['shapeblind'] if agent is only shape blind
        """
        if settings:
            hs = []
            if "colorblind" in settings:
                hs.append('colorblind')
            if "shapeblind" in settings:
                hs.append('shapeblind')
            return hs
        else:
            return []

    @staticmethod
    def same_collect_block_before_count(collect_block, collect_blocks):
        """
        TODO: finish this pydoc
        :param collect_block:
        :param collect_blocks:
        :return:
        """
        count = 0
        for cb in collect_blocks:
            if cb.get_obj_id() == collect_block.get_obj_id():
                return count

            if cb.get_colour() == collect_block.get_colour() and cb.get_shape() == collect_block.get_shape():
                count = count + 1
