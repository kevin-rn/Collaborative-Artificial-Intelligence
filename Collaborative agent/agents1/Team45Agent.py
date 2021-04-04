from typing import final, List, Dict, Final
import numpy as np  # type: ignore

from matrx.agents import StateTracker, Navigator
from matrx.actions import MoveNorth, OpenDoorAction, CloseDoorAction, GrabObject, DropObject  # type: ignore
from matrx.actions.move_actions import MoveEast, MoveSouth, MoveWest  # type: ignore
from matrx.agents.agent_utils.state import State  # type: ignore
import ast
# import pprint

from matrx.messages import Message

from bw4t.BW4TBrain import BW4TBrain


class Team45Agent(BW4TBrain):
    '''
    Agent developed by team 45
    '''

    def __init__(self, settings: Dict[str, object]):
        super().__init__(settings)
        # Disabilities
        self.colorblind = 'colorblind' in settings and settings['colorblind']
        self.shapeblind = 'shapeblind' in settings and settings['shapeblind']
        self.slow = settings['slowdown'] if 'slowdown' in settings else 1

        self.initializeBool = False
        self._moves = [MoveNorth.__name__, MoveEast.__name__, MoveSouth.__name__, MoveWest.__name__]
        self.doors = []
        self.visited_doors = []
        self.doors_of_rooms_checked_by_disabled = {}
        self.desired_blocks = {}
        self.goal_blocks = []
        self.scanning_room = False
        self.double_checking_room = False
        self.busy = False
        self.going_to_dropzone = False
        self.ranked_agent_ids = []
        self.action_queue = []
        self.picked_up_block = None
        self.map = {}
        self.is_going_to_carry = []
        self.is_going_to_visit = []
        self.wait_until_picked_up_block = False
        self.inventory_properties = {}

    def initialize(self):
        super().initialize()
        self._door_range = 1
        self.state_tracker = StateTracker(agent_id=self.agent_id)
        self.navigator = Navigator(agent_id=self.agent_id,
                                   action_set=self.action_set, algorithm=Navigator.A_STAR_ALGORITHM)

    def setup_with_state(self, state):
        objects = list(state.keys())
        # Initialize list of doors
        self.doors = [obj for obj in objects if 'is_open' in state[obj]]

        # Initialize dropzone (goal blocks)
        goal_block_ids = [obj for obj in objects if 'is_goal_block' in state[obj] and state[obj]['is_goal_block']]
        for goal_block_id in goal_block_ids:
            goal_block_dict = {'obj_id': goal_block_id}
            if not self.shapeblind:
                goal_block_dict['shape'] = state[goal_block_id]['visualization']['shape']
            if not self.colorblind:
                goal_block_dict['colour'] = state[goal_block_id]['visualization']['colour']
            self.goal_blocks.append(goal_block_dict)
        self.order_goal_blocks(state)

        # Initialize list of desired blocks and broadcast the information that this agent knows.
        desired_blocks_keys = [obj for obj in objects if
                               'is_goal_block' in state[obj] and state[obj]['is_goal_block']]
        for desired_blocks_key in desired_blocks_keys:
            desired_block_info = {}
            if not self.colorblind:
                desired_block_info['colour'] = state[desired_blocks_key]['visualization']['colour']
            if not self.shapeblind:
                desired_block_info['shape'] = state[desired_blocks_key]['visualization']['shape']
            self.desired_blocks[desired_blocks_key] = desired_block_info
        self.send_message_update_desired_blocks(self.desired_blocks)
        # print(f"desired blocks: {self.desired_blocks}")
        if len(self.ranked_agent_ids) == 0:
            self.ranking_agents(state)

        # Create map of all traversable locations.
        # This will be updated with information found by itself or other agents.
        self.map = {}
        for loc in list(self.get_traverse_map_with_rooms().keys()):
            self.map[loc] = None

    def filter_bw4t_observations(self, state):
        # Setup with state once
        if not self.initializeBool:
            self.setup_with_state(state)
            self.initializeBool = True

        # If an agent is both shape- and colorblind, let it stand still and do nothing
        if self.shapeblind and self.colorblind:
            return state
        self.parse_messages(state)

        # print(f"[{self.agent_id}] TICK {state['World']['nr_ticks']}")

        # If we are scanning a room for the first time, we only need to move toward locations that are None
        # (unless we find a desired block).
        if self.scanning_room and (not self.going_to_dropzone): # and (not self.double_checking_room):
            self.remove_unnecessary_tiles()

        # Move to drop zone if all desired blocks are collected or inventory is full
        if not self.going_to_dropzone and not self.wait_until_picked_up_block and (
                len(self.desired_blocks) == 0 or len(state[self.agent_id]['is_carrying']) == 3):
            self.move_to_dropzone(state)

        # # If we are moving to the dropzone and inventory changes, recalculate waypoints
        # if self.going_to_dropzone and len(self.inventory_properties) != len(state[self.agent_id]['is_carrying']):
        #     self.recalculate_move_to_dropzone(state)

        # Add closest door as waypoint (if there are still blocks to find and this agent is done with previous actions)
        if len(self.desired_blocks) > 0 and (not self.busy) and len(self.navigator.get_all_waypoints()) == 0:
            self.add_waypoints_to_closest_room(state)

        # If we were scanning a room and are at location of last waypoint, we can reset and go look for next room
        # Also make sure there are still blocks to find
        if not self.going_to_dropzone and len(self.desired_blocks) > 0 and self.scanning_room and self.navigator.get_upcoming_waypoints() == []:
            self.done_scanning_room(state)

        # update map based on the things the agent can see
        visible_block_id_and_loc = self.update_map_based_on_vision(state)

        if len(self.desired_blocks) > 0 or self.wait_until_picked_up_block:
            # Check if any desired blocks are visible to this agent
            self.check_if_desired_blocks_visible(state, visible_block_id_and_loc)

            # Check if the agent is standing on a desired block
            self.check_standing_on_desired_block(state, visible_block_id_and_loc)

        return state  # Why need to returning state

    def decide_on_bw4t_action(self, state: State):
        # If an agent is both shape- and colorblind, let it stand still and do nothing
        if self.shapeblind and self.colorblind:
            return None, {}

        # Update the agent's state
        self.state_tracker.update(state)

        agent_loc = state[self.agent_id]['location']
        # If all blocks that this agent might have wanted to pick up are
        if len(self.is_going_to_visit) == 0:
            self.wait_until_picked_up_block = False
        # if there are any urgent actions, do them first
        if len(self.action_queue) != 0:
            # print(f"[{self.agent_id}] Performing action from action_queue...")
            return self.action_queue.pop(0)

        # # if we picked up a block last tick, broadcast this information.
        # if self.picked_up_block is not None:
        #     self.broadcast_agent_picked_up_block(state)

        # This function handles the final dropping off of blocks.
        returnval = self.check_if_on_correct_goal_block(state, agent_loc)
        # the function check_if_on_correct_goal_block can return an action.
        # so if it returns something, perform that action.
        if returnval:
            return returnval

        # These next number of checks are only relevant if the agent is not going to the dropzone.
        if len(self.visited_doors) != 0 and not self.going_to_dropzone:
            last_door_loc = state[self.visited_doors[-1]]['location']
            # If agent is in front of the door of the room it is visiting and it is closed, open it
            # (and set scanning_room to true).
            if last_door_loc == (agent_loc[0], agent_loc[1] - 1) and not state[self.visited_doors[-1]]['is_open']:
                self.scanning_room = True
                return OpenDoorAction.__name__, {'object_id': self.visited_doors[-1]}

            # If we are standing in front of an open door corresponding to the room we are visiting,
            # continue into room (and set scanning_room to True)
            elif last_door_loc == (agent_loc[0], agent_loc[1] - 1) and state[self.visited_doors[-1]]['is_open'] and len(
                    self.navigator.get_all_waypoints()) != 0:
                self.scanning_room = True
                return self.navigator.get_move_action(self.state_tracker), {}

            # If we haven't reached the door corresponding to the room we are visiting and it is not yet open,
            # continue with the moves in the navigator
            elif last_door_loc != (agent_loc[0], agent_loc[1] - 1) and not state[self.visited_doors[-1]][
                'is_open'] and len(self.navigator.get_all_waypoints()) != 0:
                return self.navigator.get_move_action(self.state_tracker), {}


        # If we are not visiting a room and all desired blocks are found (of which we carry none), stay put.
        elif len(self.desired_blocks) == 0 and len(state[self.agent_id]['is_carrying']) == 0 and not self.wait_until_picked_up_block:
            return None, {}

        # Else continue with moves left in navigator
        if len(self.navigator.get_all_waypoints()) != 0:
            return self.navigator.get_move_action(self.state_tracker), {}

        # Default case: do nothing (when visited_doors is not empty but we shouldn't do anything)
        return None, {}

    def send_message_update_map(self, info):
        dict_to_send = {
            "agent_id": self.agent_id,
            "update_map": info
        }
        message = Message(content=dict_to_send, from_id=self.agent_id)
        self.send_message(message)

    def send_message_update_desired_blocks(self, desired_block_array):
        block_array = []
        for block_id in desired_block_array.keys():
            block_array.append({block_id: desired_block_array[block_id]})
        dict_to_send = {
            "agent_id": self.agent_id,
            "desired_blocks": block_array
        }
        message = Message(content=dict_to_send, from_id=self.agent_id)
        self.send_message(message)

    # picked_up_block is a dictionary containing the id of the block that was picked up,
    # the id of the corresponding goal block and the properties of the block (colour and shape)
    def send_message_picked_up_block(self, picked_up_block):
        dict_to_send = {
            "agent_id": self.agent_id,
            "picked_up_block": picked_up_block
        }
        message = Message(content=dict_to_send, from_id=self.agent_id)
        self.send_message(message)

    def send_message_choose_room(self, room_name):
        dict_to_send = {
            "agent_id": self.agent_id,
            "room_name": room_name
        }
        message = Message(content=dict_to_send, from_id=self.agent_id)
        self.send_message(message)

    # This message is sent if an agent has a disability and is finished scanning a certain room.
    def send_message_disabled_checked_room(self, disabled_door_dict):
        dict_to_send = {
            "agent_id": self.agent_id,
            "disabled_door": disabled_door_dict
        }
        message = Message(content=dict_to_send, from_id=self.agent_id)
        self.send_message(message)

    # This message is sent whenever an agent is planning on going to a room to doublecheck it
    # (e.g. it was already checked by an agent with different (dis)abilities)
    def send_message_finish_disabled_checked_room(self, disabled_door_dict):
        dict_to_send = {
            "agent_id": self.agent_id,
            "finish_disabled_door": disabled_door_dict
        }
        message = Message(content=dict_to_send, from_id=self.agent_id)
        self.send_message(message)

    # This method parses the messages that are received.
    def parse_messages(self, state):
        for message in self.received_messages:
            if isinstance(message, str):
                message = ast.literal_eval(message)
            # print(f"message: {message}")
            if message['agent_id'] != self.agent_id:
                # First check if we already added this agent id to the ranked_agent_ids array
                if not message['agent_id'] in self.ranked_agent_ids:
                    self.ranked_agent_ids.append(message['agent_id'])
                    self.ranked_agent_ids.sort()
                if 'desired_blocks' in message:
                    # Get list of all property names (x3) of blocks that are available in the message
                    block_properties = []
                    for block_dict in message['desired_blocks']:
                        block_properties += list(next(iter(block_dict.values())).keys())
                    if self.shapeblind and 'shape' in block_properties and message['desired_blocks'][0]:
                        for desired_block_info in message['desired_blocks']:
                            desired_block_id = next(iter(desired_block_info.keys()))
                            self.desired_blocks[desired_block_id]['shape'] = \
                                next(iter(desired_block_info.values()))['shape']
                            for goal_block_dict in self.goal_blocks:
                                if goal_block_dict['obj_id'] == desired_block_id:
                                    goal_block_dict['shape'] = next(iter(desired_block_info.values()))['shape']

                    if self.colorblind and 'colour' in block_properties:
                        for desired_block_info in message['desired_blocks']:
                            desired_block_id = next(iter(desired_block_info.keys()))
                            self.desired_blocks[desired_block_id]['colour'] = \
                                next(iter(desired_block_info.values()))['colour']
                            for goal_block_dict in self.goal_blocks:
                                if goal_block_dict['obj_id'] == desired_block_id:
                                    goal_block_dict['colour'] = next(iter(desired_block_info.values()))['colour']

                elif "picked_up_block" in message:
                    # Check if this agent is also going to carry that block (by checking if it is in inventory properties
                    duplicate = False
                    # set map location of picked up block to false
                    for inv_item_id in self.inventory_properties.keys():
                        # Check if the agent is also planning on picking up the block that corresponds to the goal block id given in the message.
                        if self.inventory_properties[inv_item_id]['goal_id'] == message['picked_up_block']['goal_block_id']:
                            # print(f"[{self.agent_id}] DUPLICATE ITEM! CHECKING IF THIS AGENT SHOULD CONCEDE AND IF THERE IS ANOTHER GOAL BLOCK WITH SAME PROPERTIES")
                            if self.ranked_agent_ids.index(self.agent_id) > self.ranked_agent_ids.index(
                                    message['agent_id']):
                                # The item is duplicate. However, first check if another desired block has exactly the same properties:
                                also_desired = False
                                for des_block_id in self.desired_blocks.keys():
                                    # Make sure that we are checking for a different goal block
                                    if des_block_id == message['picked_up_block']['goal_block_id']:
                                        continue
                                    if (self.inventory_properties[inv_item_id]['shape'] == self.desired_blocks[des_block_id]['shape']
                                    and self.inventory_properties[inv_item_id]['colour'] ==
                                    self.desired_blocks[des_block_id]['colour']):
                                        # This item is still wanted. Broadcast message as if we pick this up and update inventory info
                                        self.inventory_properties[inv_item_id]['goal_id'] = des_block_id
                                        message_to_send = {'goal_block_id': des_block_id,
                                       'picked_up_block_id': inv_item_id,
                                       'colour': self.inventory_properties[inv_item_id]['colour'],
                                       'shape': self.inventory_properties[inv_item_id]['shape']}
                                        self.send_message_picked_up_block(message_to_send)
                                        also_desired = True
                                        break
                                if not also_desired:
                                    # print(f"[{self.agent_id}] DUPLICATE ITEM, THIS AGENT SHOULDN'T PICK UP THIS BLOCK.")
                                    # Remove it from our desired block dict, inventory_properties dict and is_going_to_visit list.
                                    self.desired_blocks.pop(self.inventory_properties[inv_item_id]['goal_id'], None)
                                    self.inventory_properties.pop(inv_item_id, None)
                                    if inv_item_id in self.is_going_to_visit:
                                        self.is_going_to_visit.remove(inv_item_id)
                                    duplicate = True
                    if not duplicate:
                        # Before removing it, make sure it is actually in the list
                        if message['picked_up_block']['goal_block_id'] in self.desired_blocks.keys():
                            #     f"[{self.agent_id}] Desired blocks: {self.desired_blocks}, trying to remove {message['picked_up_block']['goal_block_id']}")
                            del self.desired_blocks[message['picked_up_block']['goal_block_id']]
                            # print(f"[{self.agent_id}] desired_blocks after removal: {self.desired_blocks}")

                        # Also make sure this agent is not in process of picking up the block with same goal block id
                        if self.picked_up_block is not None and self.picked_up_block[1] == message['picked_up_block']['goal_block_id']:
                            also_desired = False
                            for des_block_id in self.desired_blocks.keys():
                                if (self.inventory_properties[self.picked_up_block[0]]['shape'] ==
                                        self.desired_blocks[des_block_id]['shape']
                                        and self.inventory_properties[self.picked_up_block[0]]['colour'] ==
                                        self.desired_blocks[des_block_id]['colour']):
                                    # This item is still wanted. change the goal id locally and continue
                                    self.picked_up_block = (self.picked_up_block[0], des_block_id)
                                    also_desired = True
                                    break
                            if not also_desired:
                                # print(f"[{self.agent_id}] THIS AGENT SHOULDN'T PICK UP THIS BLOCK, REMOVING IT FROM QUEUE ETC")
                                # Remove it from all associated fields
                                self.inventory_properties.pop(self.picked_up_block[0], None)
                                self.action_queue.pop(0) if self.action_queue else None
                                self.is_going_to_carry.remove(self.picked_up_block[0]) if self.is_going_to_carry else None
                                self.picked_up_block = None

                    # Make sure that we remove the block they pick up from our list of blocks to visit (to handle edge case)
                    if message['picked_up_block']['picked_up_block_id'] in self.is_going_to_visit:
                        self.is_going_to_visit.remove(message['picked_up_block']['picked_up_block_id'])
                elif "room_name" in message and not self.going_to_dropzone:
                    # Only care about room updates if not all blocks are found yet.
                    # Check if agents are going to the same room
                    if len(self.visited_doors) != 0 and message['room_name'] == state[self.visited_doors[-1]][
                        'room_name']:
                        # Check ranking, the lower ranked agent (higher index) chooses a different room
                        if self.ranked_agent_ids.index(self.agent_id) > self.ranked_agent_ids.index(
                                message['agent_id']):
                            self.navigator.reset_full()
                            self.busy = False
                    else:
                        # Other agent is going to this room, add to visited doors
                        objects = list(state.keys())
                        door = [obj for obj in objects if
                                'is_open' in state[obj] and state[obj]['room_name'] == message['room_name']]
                        self.visited_doors.insert(0, door[0])
                elif "update_map" in message:

                    # Loop through all updated values in message and see if there is new information to store
                    for (loc, info) in message['update_map']:
                        if info is not None and not info:
                            self.map[loc] = False
                        else:
                            # if self.map[loc] is None:
                            self.map[loc] = {"obj_id": info['obj_id']}
                            if 'colour' in info:
                                self.map[loc]['colour'] = info['colour']
                            if 'shape' in info:
                                self.map[loc]['shape'] = info['shape']
                elif "disabled_door" in message:
                    door_dict = message['disabled_door']
                    self.doors_of_rooms_checked_by_disabled[list(door_dict.keys())[0]] = door_dict[
                        list(door_dict.keys())[0]]
                elif "finish_disabled_door" in message:
                    self.doors_of_rooms_checked_by_disabled.pop(message['finish_disabled_door']['door_id'], None)
        # Remove all messages
        self.received_messages = []

    # Remove tiles that are not None (except for tiles containing desired blocks)
    def remove_unnecessary_tiles(self):
        waypoints = [waypoint[1] for waypoint in self.navigator.get_all_waypoints()]
        necessary_waypoints = [waypoint for waypoint in waypoints if self.map[waypoint] is None or (
                self.map[waypoint] and (self.map[waypoint]['obj_id'] in self.is_going_to_visit or ('shape' not in self.map[waypoint] and not self.shapeblind) or ('colour' not in self.map[waypoint] and not self.colorblind)))]
        if len(waypoints) != len(necessary_waypoints):
            self.navigator.reset_full()
            self.navigator.add_waypoints(necessary_waypoints)

    # This function adds a waypoint to the given location.
    # If there is a closed door in the way, it only adds it if the location is in the room that the agent is visiting next.
    def waypoints_to_block(self, loc, state):
        waypoints = [loc]
        self.navigator.add_waypoint(loc)
        if self.navigator.get_move_action(self.state_tracker) is None:
            # We cannot go to the location. Probably there is a door in the way; we need to go there first
            # If there is a door in the way, this should mean the block is in the room that we are planning on visiting.
            # So we need to open that door first.
            door_loc = state[self.visited_doors[-1]]['location']
            waypoints = [(door_loc[0], door_loc[1] + 1)] + waypoints
        self.navigator.reset_full()
        return waypoints

    def is_next_block(self, state, goal_block_id):
        # self.goal_blocks is ordered (in the order that blocks need to be dropped off)
        # so we can check if the first goal_block_id in that list that has a corresponding block in the inventory is
        # equal to the goal_block_id passed as parameter
        for ordered_goal_block_dict in self.goal_blocks:
            ordered_goal_block_id = ordered_goal_block_dict['obj_id']
            # Check if it is in our inventory:
            if ordered_goal_block_id in [inv_item_val['goal_id'] for inv_item_val in
                                         self.inventory_properties.values()]:
                # Now, ordered_goal_block_id corresponds to the next block we should drop.
                return ordered_goal_block_id == goal_block_id

    # This function returns all room tiles that might have a desired block as waypoints.
    def get_potential_waypoints(self, state, closest_door_id):
        # return list of room tile ids that have (potentially desired) blocks
        objects = list(state.keys())
        curr_room = state[closest_door_id]['room_name']
        room_tiles = [obj for obj in objects if
                      'room_name' in state[obj] and state[obj]['room_name'] == curr_room and state[obj][
                          'is_traversable']]
        tile_ids = []
        for tile in room_tiles:
            tile_loc = state[tile]['location']
            # if no info is yet known about this location, add it as waypoint
            if self.map[tile_loc] is None:
                tile_ids.append(tile)

            elif self.map[tile_loc]:
                # map location corresponds to a block, check if it is potentially desired
                if self.check_if_desired(self.map[tile_loc]):
                    tile_ids.append(tile)
        return tile_ids

    # Checks whether the given block might be a desired block
    def check_if_desired(self, block_info):
        for desired_block_properties in self.desired_blocks.values():
            if 'colour' not in block_info or block_info['colour'] == desired_block_properties['colour']:
                if 'shape' not in block_info or block_info['shape'] == desired_block_properties['shape']:
                    return True
        return False

    # This function returns a list of (traversable) locations that an agent is able to see,
    # given the agent's vision range
    def get_visible_locations(self, agent_loc, vision_range):
        locs = []
        for x in range(agent_loc[0] - vision_range, agent_loc[0] + vision_range + 1):
            xdiff = abs(agent_loc[0] - x)
            for y in range(agent_loc[1] - (vision_range - xdiff), agent_loc[1] + (vision_range - xdiff) + 1):
                # Agent can theoretically see this location.
                # However, we are only interested in locations that might contain a block. So, only append visible locations
                # If they exist in the map.
                if (x, y) in self.map.keys():
                    locs.append((x, y))
        return locs

    # create a lexicographically ordered list of agent ids.
    def ranking_agents(self, state):
        objects = list(state.keys())
        agents_test = state.get_agents()
        agents = [obj for obj in objects if 'isAgent' in state[obj] and state[obj]['isAgent'] is True]
        # # Manually add own agent id if it was not added yet
        if not self.agent_id in agents:
            agents.append(self.agent_id)
        agents.sort()
        self.ranked_agent_ids = agents

    # Order the goal blocks based on dropping order
    def order_goal_blocks(self, state):
        id_and_loc = []
        for goal_block_dict in self.goal_blocks:
            id_and_loc.append((goal_block_dict, state[goal_block_dict['obj_id']]['location']))
        # Sort list of dropzones in reverse order (lowest location first)
        id_and_loc.sort(key=lambda x: x[1], reverse=True)
        self.goal_blocks = [id_loc_tuple[0] for id_loc_tuple in id_and_loc]

    # return the closest door that this agent should go to (either unvisited or this agent can doublecheck it).
    def _closest_unvisited_door(self, state: State):
        closest_dist = state['World']['grid_shape'][0] + state['World']['grid_shape'][1]
        closest_door = ""
        if len(self.doors_of_rooms_checked_by_disabled) > 0:
            # For all partially completed room, find the closest one that this agent can complete
            message_dict = {}
            for door_id in self.doors_of_rooms_checked_by_disabled.keys():
                if 'shape' in self.doors_of_rooms_checked_by_disabled[door_id] and not self.shapeblind:
                    dist = int(np.ceil(np.linalg.norm(
                        np.array(state[door_id]['location']) - np.array(
                            state[self.agent_id]['location']))))
                    if dist < closest_dist or (dist == closest_dist and len(self.visited_doors) > 0 and state[self.visited_doors[-1]]['location'][1] == state[door_id]['location'][1]):
                        message_dict = {'door_id': door_id}
                        closest_door = door_id
                        closest_dist = dist
                if 'colour' in self.doors_of_rooms_checked_by_disabled[door_id] and not self.colorblind:
                    dist = int(np.ceil(np.linalg.norm(
                        np.array(state[door_id]['location']) - np.array(
                            state[self.agent_id]['location']))))
                    if dist < closest_dist or (dist == closest_dist and len(self.visited_doors) > 0 and state[self.visited_doors[-1]]['location'][1] == state[door_id]['location'][1]):
                        message_dict = {'door_id': door_id}
                        closest_door = door_id
                        closest_dist = dist
            if closest_door != "":
                self.send_message_finish_disabled_checked_room(message_dict)
                # Remove the room from local list doors_of_rooms_checked_by_disabled
                self.doors_of_rooms_checked_by_disabled.pop(closest_door, None)
                self.double_checking_room = True
                return closest_door
        # There are no rooms that this agent can doublecheck. Find the next closest unvisited room.
        for door_id in self.doors:
            if door_id not in self.visited_doors:
                if self.slow <= 1:
                    dist = int(np.ceil(np.linalg.norm(
                        np.array(state[door_id]['location']) - np.array(
                            state[self.agent_id]['location']))))
                else:
                    dist = int(np.ceil(np.linalg.norm(
                        np.array(state[door_id]['location']) - np.array(
                            state[self.goal_blocks[-1]['obj_id']]['location']))))
                if dist < closest_dist or (dist == closest_dist and len(self.visited_doors) > 0 and state[self.visited_doors[-1]]['location'][1] == state[door_id]['location'][1]):
                    closest_door = door_id
                    closest_dist = dist
        self.double_checking_room = False
        return closest_door

    # Create a map of locations that are traversable (so this includes the room tiles)
    def get_traverse_map_with_rooms(self):
        width, length = self.state.get_world_info()['grid_shape']
        coords = [(x, y) for x in range(width) for y in range(length)]
        traverse_map = {c: True for c in coords}
        intrav_objs = self.state.get_with_property(props={'is_traversable': False}, combined=False)
        for o in intrav_objs:
            traverse_map[(o['location'][0], o['location'][1])] = False

        return traverse_map

    # Add locations of drop zones of which this agent is holding the block to the navigator.
    def move_to_dropzone(self, state):
        self.navigator.reset_full()
        for goal_block_dict in self.goal_blocks:
            goal_block_id = goal_block_dict['obj_id']
            # Check if this agent is carrying corresponding block:
            if goal_block_id in [inv_item_val['goal_id'] for inv_item_val in self.inventory_properties.values()]:
                self.navigator.add_waypoint(state[goal_block_id]['location'])
        # print(f"[{self.agent_id}] desired blocks all found or inventory full. visited doors: {self.visited_doors}")
        # print(f"[{self.agent_id}] inventory: {state[self.agent_id]['is_carrying']}")
        # Remove last visited room
        # (since we probably didn't finish scanning entire room and possibly need to go back)
        self.visited_doors.pop()
        self.going_to_dropzone = True
        # print(f"self.going_to_dropzone is: {self.going_to_dropzone}")

    # Add locations of drop zones of which this agent is holding the block to the navigator again.
    # This function is only called if the inventory of the agent changed after calling move_to_dropzone.
    def recalculate_move_to_dropzone(self, state):
        self.navigator.reset_full()
        for goal_block_dict in self.goal_blocks:
            goal_block_id = goal_block_dict['obj_id']
            # Check if this agent is carrying corresponding block:
            if goal_block_id in [inv_item_val['goal_id'] for inv_item_val in self.inventory_properties.values()]:
                self.navigator.add_waypoint(state[goal_block_id]['location'])
        # self.visited_doors.pop()

    # Add waypoint to (below the) door and room tiles (that might have desired blocks) of the room this agent is going to visit.
    def add_waypoints_to_closest_room(self, state):
        closest_door_id = self._closest_unvisited_door(state)
        if closest_door_id != "":
            # Find list of places that have no information or contain (potentially desired) blocks, these should be visited
            room_tiles = self.get_potential_waypoints(state, closest_door_id)
            if len(room_tiles) > 0:
                door_loc = state[closest_door_id]['location']
                door_loc = (door_loc[0], door_loc[1] + 1)
                self.navigator.add_waypoint(door_loc)
                for tile in room_tiles:
                    self.navigator.add_waypoint(state[tile]['location'])

                self.visited_doors.append(closest_door_id)
                self.busy = True
                self.send_message_choose_room(state[closest_door_id]['room_name'])
            else:
                # Room contains no interesting things. Send a message as if we are checking it out so no other agent
                # will visit it either.
                self.send_message_choose_room(state[closest_door_id]['room_name'])
                self.visited_doors.append(closest_door_id)
                # Then, call this function again to find next door that is available
                self.add_waypoints_to_closest_room(state)

        # else:
            # print(
            #     f"[{self.agent_id}] Currently no rooms to visit. Waiting until all blocks are found or need to doublecheck room.")

    # Once an agent is done scanning a room, notify other agents and find next action.
    def done_scanning_room(self, state):
        # We have scanned entire room
        self.scanning_room = False
        self.navigator.reset_full()
        self.busy = False
        # print(f"[{self.agent_id}] Finished scanning room!")
        # If this agent was not doublechecking a room and has disabilities, add room to other dict.
        if self.visited_doors[-1] in self.doors_of_rooms_checked_by_disabled.keys():
            del self.doors_of_rooms_checked_by_disabled[self.visited_doors[-1]]
        elif not self.double_checking_room:
            dict_of_disabilities = {}
            if self.colorblind:
                dict_of_disabilities['colour'] = True
            if self.shapeblind:
                dict_of_disabilities['shape'] = True
            if len(dict_of_disabilities) > 0:
                self.doors_of_rooms_checked_by_disabled[self.visited_doors[-1]] = dict_of_disabilities
                self.send_message_disabled_checked_room({self.visited_doors[-1]: dict_of_disabilities})

        # Add waypoint to next room
        self.scanning_room = False
        self.add_waypoints_to_closest_room(state)

    # Check the locations that the agent can see and update the map accordingly. Send updated values to other agents.
    def update_map_based_on_vision(self, state):
        # Check all visible locations for (desired) blocks
        locs = self.get_visible_locations(state[self.agent_id]['location'], 2)
        updated_locs = []
        objects = list(state.keys())
        visible_block_id_and_loc = [(obj, state[obj]['location']) for obj in objects if
                                    'is_movable' in state[obj] and 'isAgent' not in state[obj] and state[obj][
                                        'is_movable'] and
                                    state[obj]['location'] in locs]
        # Update map according to vision:
        # Update info about visible blocks
        for (block_id, loc) in visible_block_id_and_loc:
            updated = False
            if self.map[loc] is None or not self.map[loc]:
                self.map[loc] = {"obj_id": block_id}
                updated = True
            if not self.colorblind and 'colour' not in self.map[loc]:
                self.map[loc]['colour'] = state[block_id]['visualization']['colour']
                updated = True
            if not self.shapeblind and 'shape' not in self.map[loc]:
                self.map[loc]['shape'] = state[block_id]['visualization']['shape']
                updated = True
            if loc in locs:
                locs.remove(loc)
            if updated:
                updated_locs.append(loc)

        # Update info about seen locations with nothing of interest
        for loc in locs:
            if self.map[loc] is None or self.map[loc]:
                self.map[loc] = False
                updated_locs.append(loc)

        # Send updated info to other agents (if any location was updated)
        if len(updated_locs) > 0:
            self.send_message_update_map([(loc, self.map[loc]) for loc in updated_locs])
        return visible_block_id_and_loc

    # Given a list of blocks that are visible to the agent, check if any of them are desired.
    # If so, add waypoint to that block.
    def check_if_desired_blocks_visible(self, state, visible_block_id_and_loc):
        # check if we can see a desired block (using just updated map)
        for (block_id, loc) in visible_block_id_and_loc:
            # Check if block is desired (and not yet (in process of ) picking up)
            # This if check also makes sure that we only add a block as waypoint once
            if block_id not in self.is_going_to_carry and block_id not in self.inventory_properties.keys():  # TODO: first check of this if statement is maybe redundant
                if 'colour' in self.map[loc] and 'shape' in self.map[loc]:
                    for desired_block_id in self.desired_blocks.keys():
                        if (self.map[loc]['shape'] == self.desired_blocks[desired_block_id]['shape']
                                and self.map[loc]['colour'] == self.desired_blocks[desired_block_id][
                                    'colour']):
                            # The block we see is desired. If it is in a room that we are (going to) visit(ing), we should pick it up!
                            # Priority should be moving there.
                            self.is_going_to_visit.append(block_id) if block_id not in self.is_going_to_visit else None
                            if len(self.visited_doors) > 0 and state[self.visited_doors[-1]]['room_name'] == \
                                    state[block_id]['name'].split()[2]:
                                tick = state['World']['nr_ticks']
                                prev_waypoints = [waypoint[1] for waypoint in self.navigator.get_all_waypoints()]
                                self.navigator.reset_full()
                                priority_waypoints = self.waypoints_to_block(loc, state)
                                new_waypoints = priority_waypoints + prev_waypoints

                                self.navigator.add_waypoints(new_waypoints)
                                self.is_going_to_visit.append(block_id) if block_id not in self.is_going_to_visit else None

                                # Claim the block; broadcast that agent is going to pick up this block
                                self.inventory_properties[block_id] = {'colour': self.map[loc]['colour'],
                                                                            'shape': self.map[loc]['shape'],
                                                                            'goal_id': desired_block_id}
                                # We are going to pick up this block. Add info to some fields (is_going_to_carry and picked_up_block),
                                # and append action of picking up the block to the action queue
                                # print(f"[{self.agent_id}] Claiming a block {block_id}!!!")
                                # Broadcast the fact that we are going to pick up a block
                                message_to_send = {'goal_block_id': desired_block_id,
                                                   'picked_up_block_id': block_id,
                                                   'colour': self.map[loc]['colour'],
                                                   'shape': self.map[loc]['shape']}
                                del self.desired_blocks[desired_block_id]
                                # Make sure we don't start moving towards dropzone until we have picked up this block
                                self.wait_until_picked_up_block = True
                                self.send_message_picked_up_block(message_to_send)
                                break

    # Check if the agent is standing on a desired block. If so, add picking up action to action queue.
    def check_standing_on_desired_block(self, state, visible_block_id_and_loc):
        # Check if we are standing on a desired block
        agent_loc = state[self.agent_id]['location']
        curr_block_id = [obj for (obj, loc) in visible_block_id_and_loc if
                         loc == agent_loc]
        if len(curr_block_id) > 0:
            curr_block_id = curr_block_id[0]
            # Check if block is desired (and not yet (in process of ) picking up)
            if curr_block_id not in self.is_going_to_carry:
                # for desired_block_id in [self.inventory_properties[b_id]['goal_id'] for b_id in self.is_going_to_visit if b_id in self.inventory_properties.keys()]:
                #     if ('colour' in self.map[agent_loc] and 'shape' in self.map[agent_loc] and self.map[agent_loc][
                #         'shape'] == self.inventory_properties[curr_block_id]['shape']
                #             and self.map[agent_loc]['colour'] == self.inventory_properties[curr_block_id][
                #                 'colour']):
                if curr_block_id in self.is_going_to_visit: # and curr_block_id in self.inventory_properties.keys():
                    # self.inventory_properties[curr_block_id] = {'colour': self.map[agent_loc]['colour'],
                    #                                             'shape': self.map[agent_loc]['shape'],
                    #                                             'goal_id': desired_block_id}
                    # We are going to pick up this block. Add info to some fields (is_going_to_carry and picked_up_block),
                    # and append action of picking up the block to the action queue
                    self.is_going_to_carry.append(curr_block_id)
                    # print(f"[{self.agent_id}] Picking up a block!!!")
                    # Store fact that we picked up block TODO: try to get rid of self.picked_up_block
                    self.picked_up_block = (curr_block_id, self.inventory_properties[curr_block_id]['goal_id'])
                    # Remove block from self.is_going_to_visit
                    self.is_going_to_visit.remove(curr_block_id)
                    self.action_queue.append((GrabObject.__name__, {'object_id': curr_block_id}))


    # Broadcast fact that this agent picked up a block last tick
    # def broadcast_agent_going_to_pick_up_block(self, block_id, desired_block_id):
    #         message_to_send = {'goal_block_id': goal_block_id,
    #                            'picked_up_block_id': carried_block_info['obj_id'],
    #                            'colour': goal_block_dict['colour'],
    #                            'shape': goal_block_dict['shape']}
    #         self.send_message_picked_up_block(message_to_send)
    #         self.picked_up_block = None
    #     # else:
        #     # We probably picked it up but it was duplicate so we dropped it immediately.
        #     # Update picked_up_block field accordingly.
        #     self.picked_up_block = None

    # This function handles the final dropping of blocks. It checks if the agent should drop a block on the current location
    # (if the corresponding block is in its inventory), if it should wait on this location or if it should move.
    def check_if_on_correct_goal_block(self, state, agent_loc):
        # Loop over goal blocks and see if we are on one of the tiles:
        for goal_block_dict in self.goal_blocks:
            goal_block_id = goal_block_dict['obj_id']
            if agent_loc == state[goal_block_id]['location']:

                objects = list(state.keys())
                block_below_id = [obj for obj in objects if
                                  ('is_movable' in state[obj]) and ('isAgent' not in state[obj]) and (state[obj][
                                                                                                          'is_movable'] is True) and
                                  state[obj]['location'] == (agent_loc[0], agent_loc[1] + 1)]
                # print(f"[{self.agent_id}] standing above block: {block_below_id}")
                # Check if there is already a block below this spot (or we are at the lowest spot)
                if (agent_loc == state[self.goal_blocks[0]['obj_id']]['location']
                        or len(block_below_id) == 1):
                    # Now check if the corresponding block that needs to be placed on this location is next up in our inventory
                    if (goal_block_id in [inv_item_val['goal_id'] for inv_item_val in
                                          self.inventory_properties.values()]
                            and self.navigator.get_current_waypoint() == agent_loc):
                        block_id_to_drop = [inv_item_id for inv_item_id in self.inventory_properties.keys() if
                                            self.inventory_properties[inv_item_id]['goal_id'] == goal_block_id][0]
                        # Remove this block from inventory_properties
                        self.inventory_properties.pop(block_id_to_drop, None)
                        # print(f"[{self.agent_id}] DROPPING OBJECT: {block_id_to_drop}")
                        return DropObject.__name__, {'object_id': block_id_to_drop}
                    else:
                        # The goal block we are standing on still needs to be filled, but we don't have the block (or we need to drop another block first).
                        # Continue with navigation (if there is a move left).
                        if len(self.navigator.get_upcoming_waypoints()) > 0:
                            return self.navigator.get_move_action(self.state_tracker), {}
                        else:
                            return None, {}
                else:
                    # Either we are at a spot that we need to go to and will have to wait here until the block below is placed,
                    # or we were still navigating to correct spot in drop zone (and walked across a drop zone square in the process)
                    # So now check if the corresponding block that needs to be placed on this location is in our inventory
                    if goal_block_id in [inv_item_val['goal_id'] for inv_item_val in
                                         self.inventory_properties.values()] and self.navigator.get_current_waypoint() == agent_loc:
                        # We have the corresponding block, so we need to wait here until block below is placed.
                        return None, {}
                    else:
                        # Continue navigation
                        return self.navigator.get_move_action(self.state_tracker), {}
