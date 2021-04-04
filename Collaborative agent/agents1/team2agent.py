from typing import Dict
import random  # type: ignore
import math
import sys
import numpy as np  # type: ignore
import ast
from enum import Enum

from matrx.agents import StateTracker, Navigator
from matrx.agents.agent_utils.state import State
from matrx.agents.agent_utils.navigator import AStarPlanner
from matrx.actions import OpenDoorAction, GrabObject, DropObject
from matrx.actions.move_actions import MoveNorth, MoveEast, MoveSouth, MoveWest  # type: ignore
from matrx.messages import Message

from bw4t.BW4TBrain import BW4TBrain


class FSMState(Enum):
    START = 0
    SELECTING = 1
    TIE_BREAKING = 2
    WALKING = 3
    DROPPING = 4
    FINISH = 5
    STOP = 6


def print_map(state: State):
    print("Extracting the map")
    traverse_map = state.get_traverse_map()
    width, length = state.get_world_info()['grid_shape']
    for y in range(length):
        for x in range(width):
            if traverse_map[(x, y)]:
                print("*", end="")
            else:
                print(" ", end="")
        print()


def calculate_room_traversal_waypoints(state: State, room_name):
    room_objects = state.get_room_objects(room_name)
    room_tiles = []
    for room_object in room_objects:
        room_tiles.append(room_object['location'])

    left = sys.maxsize / 2
    right = -sys.maxsize / 2
    top = sys.maxsize / 2
    bottom = -sys.maxsize / 2
    for room_tile in room_tiles:
        if room_tile[0] < left:
            left = room_tile[0]
        elif room_tile[0] > right:
            right = room_tile[0]
        if room_tile[1] < top:
            top = room_tile[1]
        elif room_tile[1] > bottom:
            bottom = room_tile[1]
    waypoints: [(int, int)] = []
    if (right - left) < 3:
        if (bottom - top) < 3:
            waypoints.append((left + ((right - left) / 2),
                              top + ((bottom - top) / 2)))
        else:
            waypoints.append(
                (left + math.floor((right - left) / 2), top + 1))
            waypoints.append(
                (left + math.floor((right - left) / 2), bottom - 1))
    elif (bottom - top) < 4:
        waypoints.append(
            (left + 1, math.floor(top + ((bottom - top) / 2))))
        waypoints.append(
            (right - 1, math.floor(top + ((bottom - top) / 2))))
    else:
        while ((bottom - 1) - (top + 1)) > 0:
            waypoints.append((left + 1, top + 1))
            waypoints.append((right - 1, top + 1))
            top += 3
        waypoints.append((left + 1, bottom - 1))
        waypoints.append((right - 1, bottom - 1))
    return waypoints


def get_teammate_ids(state: State, own_id):
    teammate_ids = []
    for key in state:
        if 'isAgent' in state[key] and key != own_id:
            teammate_ids.append(key)
    return teammate_ids


class GoalBlock:
    id = None
    location = None
    shape = None
    color = None

    def __init__(self, location, shape, color, id=None):
        self.id = id
        self.location = location
        self.shape = shape
        self.color = color


def get_goal_blocks(state: State):
    goal_blocks = []
    for x in state['visualization']:
        if 'is_goal_block' in x and x['is_goal_block'] is True:
            id = x['obj_id']
            location = x['location']
            shape = None
            color = None
            if 'shape' in x['visualization']:
                shape = x['visualization']['shape']
            if 'colour' in x['visualization']:
                color = x['visualization']['colour']
            goal_blocks.append(GoalBlock(location, shape, color, id))
    return goal_blocks


def deep_copy_goal_blocks(goal_blocks: [GoalBlock]):
    copy = []
    for goal_block in goal_blocks:
        copy.append(goal_block)
    return copy


class Tiles(Enum):
    GROUND = 0
    WALL = 1
    ROOM = 2
    DOOR = 3


def generate_room_map(state):
    room_map = create_map(state)
    room_map = fill_walls_info(state, room_map)
    room_map = fill_rooms_location(state, room_map)
    return room_map


def create_map(state: State):
    length, width = state.get_world_info()['grid_shape']
    mapped_locations = [[Tiles.GROUND for _ in range(
        width)] for _ in range(length)]
    return mapped_locations


def fill_rooms_location(state: State, room_map):
    all_room_names = state.get_all_room_names()
    for room_name in all_room_names:
        room_details = state.get_room_objects(room_name)
        for detail in room_details:
            x, y = detail.get('location')
            room_map[x][y] = Tiles.ROOM
    return room_map


def fill_walls_info(state: State, room_map):
    tiles = state.get_traverse_map()
    width, length = state.get_world_info()['grid_shape']
    for y in range(length):
        for x in range(width):
            if not tiles[(x, y)]:
                room_map[x][y] = Tiles.WALL
    return room_map


def print_room_map(state: State, room_map):
    print("Printing self.mapped_locations")
    width, length = state.get_world_info()['grid_shape']
    for y in range(length):
        row = ""
        for x in range(width):
            row += str(room_map[x][y].value)
        print(row)


class RoomInfo:
    room_name = None
    door_location = None
    door = None
    porch_location = None
    selected = False
    visited = False
    visited_by_color_blind = False
    visited_by_shape_blind = False

    def __init__(self, room_name, door_location, porch_location, selected, visited, visited_by_color_blind,
                 visited_by_shape_blind, door):
        self.room_name = room_name
        self.door_location = door_location
        self.door = door
        self.porch_location = porch_location
        self.selected = selected
        self.visited = visited
        self.visited_by_color_blind = visited_by_color_blind
        self.visited_by_shape_blind = visited_by_shape_blind

    def __eq__(self, other):
        return isinstance(other, self.__class__) and getattr(other, 'room_name', None) == self.room_name


def find_room_info(state: State, room_map):
    room_infos = []
    doors = []
    for i in state.get_all_room_names():
        if i != "world_bounds":
            doors.append(state.get_room_doors(i))
    doors.sort(key=lambda t: t[0]['location'][0] + t[0]['location'][1])
    porches = []
    for k in doors:
        x = k[0]['location'][0]
        y = k[0]['location'][1]
        if room_map[x + 1][y] is Tiles.GROUND:
            porches.append((x + 1, y))
        elif room_map[x - 1][y] is Tiles.GROUND:
            porches.append((x - 1, y))
        elif room_map[x][y + 1] is Tiles.GROUND:
            porches.append((x, y + 1))
        elif room_map[x][y - 1] is Tiles.GROUND:
            porches.append((x, y - 1))
    for k in range(len(doors)):
        room_infos.append(
            RoomInfo(doors[k][0]['room_name'], doors[k][0]['location'], porches[k], False, False, False, False,
                     state.get_room_doors(doors[k][0]['room_name'])[0]))

    return room_infos


def rearrange_destination(agent_location: (int, int), room_infos: [RoomInfo]):
    room_info_distances = []
    for room_info in room_infos:
        room_info_distances.append(
            (manhattan_distance_room(agent_location, room_info), room_info))
    room_info_distances.sort(key=lambda t: t[0])
    room_infos = []
    for room_info_distance in room_info_distances:
        room_infos.append(room_info_distance[1])
    return room_infos


def manhattan_distance_room(agent_location, room_info: RoomInfo):
    return abs(agent_location[0] - room_info.porch_location[0]) + abs(agent_location[1] - room_info.porch_location[1])


def get_nearby_doors(state: State, agent_id):
    # Get all doors from the perceived objects
    objects = list(state.keys())
    doors = [obj for obj in objects if 'is_open' in state[obj]]
    doors_in_range = []
    for object_id in doors:
        # Select range as just enough to grab that object
        dist = int(
            np.ceil(np.linalg.norm(np.array(state[object_id]['location']) - np.array(state[agent_id]['location']))))
        if dist <= 1:
            doors_in_range.append(object_id)
    return doors_in_range


class ShapeType(Enum):
    RECTANGLE = 0
    TRIANGLE = 1
    CIRCLE = 2


class Shape:
    def __init__(self, block_id, location, shape, color):
        self.block_id = block_id
        self.location = location
        self.shape = shape
        self.color = color

    def __str__(self):
        return "Shape has id: % s at location: % s with shape: % s and color: % s" % (
            self.block_id, self.location, ShapeType(self.shape), self.color)

    def __repr__(self):
        return "Shape has id: % s at location: % s with shape: % s and color: % s" % (
            self.block_id, self.location, ShapeType(self.shape), self.color)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and getattr(other, 'block_id', None) == self.block_id

    # checks if the shape is one our bot is looking for
    def is_required(self, req):
        if self.shape is None or self.color is None:
            return False
        else:
            return (req.shape == self.shape) and (req.color == self.color)


def manhattan_distance_shape(agent_location, shape: Shape):
    return abs(agent_location[0] - shape.location[0]) + abs(agent_location[1] - shape.location[1])


# gets all the near objects that our agent can see with their shape and color and their ids.
def get_close_objects(state: State, shapeblind: bool, colorblind: bool):
    objects = list(state.keys())
    shape_infos = []
    for key in objects:
        if key.startswith('Block_in_room'):
            shape = state.__getitem__(key)
            if shapeblind:
                shape_type = None
            else:
                shape_type = shape['visualization']['shape']
            if colorblind:
                shape_color = None
            else:
                shape_color = shape['visualization']['colour']

            t_obj = Shape(
                key, shape['location'], shape_type, shape_color)
            shape_infos.append(t_obj)

    return shape_infos


def find_goal_block(agent_location, located_shapes: [Shape], goal_blocks: [GoalBlock]):
    if len(located_shapes) > 0:
        for shape in located_shapes:
            for goal in goal_blocks:
                if shape.is_required(goal) and manhattan_distance_shape(agent_location, shape) <= 1:
                    return True, shape, goal
    return False, None, None


def generate_update_map_message(dict, agent_id, colorblind, shapeblind, teammate_ids):
    content = {
        'agent_id': agent_id,
        'update_map': []
    }
    # TODO add squares we have seen without a block on it
    for item in dict:
        if 'Block_in_room' in item:
            location = dict[item]['location']

            block_info = {'obj_id': dict[item]['obj_id']}
            if colorblind:
                pass
            else:
                block_info['colour'] = dict[item]['visualization']['colour']
            if shapeblind:
                pass
            else:
                block_info['shape'] = dict[item]['visualization']['shape']
            content['update_map'].append((location, block_info))
    message = Message(content=content, from_id=agent_id, to_id=teammate_ids)
    return message


def generate_goal_block_message(desired_blocks, agent_id, colorblind, shapeblind, teammate_ids):
    content = {
        'agent_id': agent_id,
        'desired_blocks': []
    }

    for block in desired_blocks:

        goal_block_info = {block.id: {
            "colour": block.color, "shape": block.shape}}
        if not block.color:
            del goal_block_info[block.id]["colour"]
        if block.shape is None:
            del goal_block_info[block.id]["shape"]
        content['desired_blocks'].append(goal_block_info)

    return Message(content=content, from_id=agent_id, to_id=teammate_ids)


def generate_selected_room_message(room_infos, selected_room_index, agent_id, teammate_ids):
    content = {
        'agent_id': agent_id,
        'room_name': room_infos[selected_room_index].room_name}

    return Message(content=content, from_id=agent_id, to_id=teammate_ids)


def generate_pickeup_object_message(shape, goal, agent_id, teammate_ids):
    content = {
        'agent_id': agent_id,
        'picked_up_block': {'goal_block_id': goal.id, 'picked_up_block_id': shape.block_id, 'shape': shape.shape,
                            'colour': shape.color}
    }

    return Message(content=content, from_id=agent_id, to_id=teammate_ids)


def generate_disabled_door_message(state, selected_room: RoomInfo, color_blind, shape_blind, agent_id,
                                   teammate_ids):
    door_name = selected_room.door.get("obj_id")
    disabilty = {}
    if (color_blind):
        disabilty = {"colour": True}
    elif (shape_blind):
        disabilty = {"shape": True}
    content = {
        'agent_id': agent_id,
        'disabled_door': {door_name: disabilty}
    }

    return Message(content=content, from_id=agent_id, to_id=teammate_ids)


def generate_finish_disabled_door_message(selected_room: RoomInfo, agent_id, teammate_ids):
    door_name = selected_room.door.get("obj_id")
    content = {
        'agent_id': agent_id,
        'finish_disabled_door': {'door_id': door_name}
    }

    return Message(content=content, from_id=agent_id, to_id=teammate_ids)


def check_if_items_in_inventory(state, agent_id):
    if state[agent_id].get('is_carrying'):
        return True
    return False


def get_waypoint_finish(state: State):
    dict = state.as_dict()
    drop_off_locations: (int, int) = []
    for entry in dict:
        if 'Drop_off' in entry:
            drop_off_locations.append(dict[entry]['location'])
    drop_off_locations.sort(key=lambda t: t[1])
    drop_off_location = drop_off_locations[math.floor(
        len(drop_off_locations) / 2)]
    return drop_off_location


def order_goal_blocks(goal_blocks: [GoalBlock]):
    to_order = []
    for goal_block in goal_blocks:
        to_order.append((-goal_block.location[1], goal_block))
    to_order.sort(key=lambda t: t[0])
    result = []
    for t in to_order:
        result.append(t[1])
    return result


class Team2Agent(BW4TBrain):

    def __init__(self, settings: Dict[str, object]):
        super().__init__(settings)

        # Navigation
        self._moves = [MoveNorth.__name__, MoveEast.__name__,
                       MoveSouth.__name__, MoveWest.__name__]
        self._path_planner = AStarPlanner(
            action_set=self._moves, metric=AStarPlanner.EUCLIDEAN_METRIC)
        self.state_tracker = None
        self.navigator = None
        # list of waypoints we are moving towards
        self.__waypoints: [(int, int)] = [(1, 8)]
        self.__agent_location: (int, int) = None

        # FSM
        self.__fsm_state: FSMState = FSMState.START

        # Handicaps
        self.__shape_blind: bool = False
        self.__color_blind: bool = False
        self.__slowed_down: bool = False
        for handicap in settings:
            if handicap == 'colorblind':
                self.__color_blind = True
            elif handicap == 'shapeblind':
                self.__shape_blind = True
            elif handicap == 'slowdown':
                self.__slowed_down = True

        # World info
        self.__located_shapes: [Shape] = []
        self.__inventory: [(Shape, GoalBlock)] = []

        # the ids used to send out messages
        self.__teammate_ids = []
        # a list of blocks that are needed to finish the world
        self.__goal_blocks_needed: [GoalBlock] = []
        self.__goal_blocks: [GoalBlock] = []
        # list of RoomInfo objects containing the locations of the porches and info about the bots visiting/visited
        self.__room_infos: [RoomInfo] = []
        # the last selected room for tie breaking with other groups
        self.__selected_room: RoomInfo = None
        # list of all rooms in the world
        self.__all_rooms: [RoomInfo] = []

    # noinspection PyFinal
    def initialize(self):
        super().initialize()
        self.state_tracker = StateTracker(agent_id=self.agent_id)
        self.navigator = Navigator(agent_id=self.agent_id, action_set=self.action_set,
                                   algorithm=Navigator.A_STAR_ALGORITHM)
        self.plan_path(self.__waypoints.pop())

    def filter_bw4t_observations(self, state: State) -> State:
        self.state_tracker.update(state)
        self.update_visited_objects(state)
        self.__agent_location = state[self.agent_id]['location']

        if self.received_messages:
            # print('message received')
            for message in self.received_messages:
                try:
                    if isinstance(message, str):
                        message = ast.literal_eval(message)
                except:
                    print("Could not parse string message!")
                if 'update_map' in message:
                    self.process_update_map_message(message)
                if 'desired_blocks' in message:
                    self.process_desired_block_message(message)
                if 'picked_up_block' in message:
                    self.process_picked_up_block_message(message)
                if 'room_name' in message:
                    self.process_room_name_message(message)
                if 'disabled_door' in message:
                    self.process_disabled_door_message(message)
                if 'finish_disabled_door' in message:
                    self.process_finish_disabled_door_message(message)

        # No ties had to been broken in the messages so we can safely start walking
        if self.__fsm_state == FSMState.TIE_BREAKING:
            self.__fsm_state = FSMState.WALKING

        update_map_message = generate_update_map_message(state.as_dict(), self.agent_id, self.__color_blind,
                                                         self.__shape_blind, self.__teammate_ids)
        self.send_message(update_map_message)
        self.received_messages = []
        return state

    def process_update_map_message(self, message):
        for block_tuple in message['update_map']:
            if block_tuple[1]:
                block = Shape(block_tuple[1]['obj_id'], block_tuple[0], block_tuple[1].get('shape', None),
                              block_tuple[1].get('colour', None))
                if block not in self.__located_shapes:
                    self.__located_shapes.append(block)
                else:
                    for located_shape in self.__located_shapes:
                        if located_shape.block_id == block.block_id:
                            if located_shape.color is None:
                                located_shape.color = block.color
                            if located_shape.shape is None:
                                located_shape.shape = block.shape

    def process_desired_block_message(self, message):
        for block in message['desired_blocks']:
            for goal_block_name in block:
                goal_block_colour = block[goal_block_name].get(
                    'colour', None)
                goal_block_shape = block[goal_block_name].get(
                    'shape', None)
                for known_goal_block in self.__goal_blocks_needed:
                    if known_goal_block.id == goal_block_name:
                        if known_goal_block.shape is None:
                            known_goal_block.shape = goal_block_shape
                        if known_goal_block.color is None:
                            known_goal_block.color = goal_block_colour
                self.__goal_blocks = deep_copy_goal_blocks(self.__goal_blocks)

    def process_picked_up_block_message(self, message):
        to_be_removed = None
        for goal_block in self.__goal_blocks_needed:
            block_shape = message['picked_up_block']['shape']
            block_colour = message['picked_up_block']['colour']
            if goal_block.shape == block_shape and goal_block.color == block_colour:
                to_be_removed = goal_block
        try:
            self.__goal_blocks_needed.remove(to_be_removed)
        except:
            pass
        if len(self.__goal_blocks_needed) == 0:
            self.__fsm_state = FSMState.DROPPING

    def process_room_name_message(self, message):
        if self.__fsm_state == FSMState.TIE_BREAKING and message[
            'room_name'] == self.__selected_room.room_name and self.agent_id > message['agent_id']:
            self.__waypoints = []
            self.__fsm_state = FSMState.SELECTING

        to_be_removed = None
        for room_info in self.__room_infos:
            if room_info.room_name == message['room_name']:
                to_be_removed = room_info
        if to_be_removed is not None:
            self.__room_infos.remove(to_be_removed)

    def process_disabled_door_message(self, message):
        info = message.get('disabled_door')
        for door in info:
            another_agent_disability = info[door]
            color_blind = another_agent_disability.get('colour', False)
            shape_blind = another_agent_disability.get('shape', False)
            if (color_blind and not color_blind == self.__color_blind) or (
                    shape_blind and not shape_blind == self.__shape_blind):
                # Other agent is has a different disability, process it
                for room_info in self.__all_rooms:
                    if room_info.door.get("obj_id") == door:
                        # Re-add the room
                        room_info.visited_by_color_blind = color_blind
                        room_info.visited_by_shape_blind = shape_blind
                        self.__room_infos.append(room_info)

        return

    def process_finish_disabled_door_message(self, message):
        for room_info in self.__room_infos:
            door_id = message['finish_disabled_door']['door_id']
            if door_id.startswith(room_info.room_name):
                self.__room_infos.remove(room_info)
        pass

    def decide_on_bw4t_action(self, state: State):
        return self.step(state)

    def step(self, state: State):
        result = None
        if self.__fsm_state == FSMState.START:
            result = self.start(state)
        elif self.__fsm_state == FSMState.SELECTING:
            result = self.select(state)
        elif self.__fsm_state == FSMState.WALKING:
            result = self.walk(state)
        elif self.__fsm_state == FSMState.DROPPING:
            result = self.drop(state)
        elif self.__fsm_state == FSMState.FINISH:
            result = self.finish(state)
        elif self.__fsm_state == FSMState.STOP:
            result = self.stop(state)

        return result

    def start(self, state: State):
        # print("start")
        self.__teammate_ids = get_teammate_ids(state, self.agent_id)
        self.__goal_blocks_needed = get_goal_blocks(state)
        self.__goal_blocks = deep_copy_goal_blocks(self.__goal_blocks_needed)

        goal_blocks_message = generate_goal_block_message(self.__goal_blocks_needed, self.agent_id, self.__color_blind,
                                                          self.__shape_blind, self.__teammate_ids)
        self.send_message(goal_blocks_message)

        room_map = generate_room_map(state)
        self.__room_infos = find_room_info(state, room_map)
        self.__all_rooms = find_room_info(state, room_map)

        selected_room_index = self.get_first_room_index()

        selected_room_message = generate_selected_room_message(
            self.__room_infos, selected_room_index, self.agent_id, self.__teammate_ids)
        self.send_message(selected_room_message)

        self.set_next_waypoints_room(state, selected_room_index)

        self.plan_path(self.__waypoints[0])

        self.__fsm_state = FSMState.TIE_BREAKING
        return self.get_next_movement()

    def select(self, state):
        # print("selecting")

        if len(self.__room_infos) == 0:
            self.__fsm_state = FSMState.DROPPING
            return self.drop(state)

        self.__room_infos: [RoomInfo] = rearrange_destination(
            self.__agent_location, self.__room_infos)
        selected_room_index = 0

        selected_room_message = generate_selected_room_message(
            self.__room_infos, selected_room_index, self.agent_id, self.__teammate_ids)
        self.send_message(selected_room_message)

        self.set_next_waypoints_room(state, selected_room_index)

        self.plan_path(self.__waypoints[0])
        self.__fsm_state = FSMState.TIE_BREAKING
        return self.get_next_movement()

    def walk(self, state):
        # print("walking")

        for doorId in get_nearby_doors(state, self.agent_id):
            if not state[doorId]['is_open']:
                return OpenDoorAction.__name__, {'object_id': doorId}

        found_block, shape, goal = find_goal_block(
            self.__agent_location, self.__located_shapes, self.__goal_blocks_needed)
        if found_block:
            return self.grab_shape_command(shape, goal)

        if len(self.__waypoints) == 0:
            print("SHOULD NOT HAPPEN")
            self.__fsm_state = FSMState.SELECTING
            return self.select(state)

        if self.__agent_location == self.__waypoints[0]:
            del (self.__waypoints[0])
            if len(self.__waypoints) == 0:
                self.send_disabled_door_messages(state)
                ##
                self.__fsm_state = FSMState.SELECTING
                return self.select(state)
            else:
                self.plan_path(self.__waypoints[0])

        return self.get_next_movement()

    def send_disabled_door_messages(self, state):
        if self.__shape_blind and self.__color_blind:
            finish_room_disabled_message = generate_disabled_door_message(state,
                                                                          self.__selected_room,
                                                                          self.__color_blind,
                                                                          self.__shape_blind,
                                                                          self.agent_id,
                                                                          self.__teammate_ids)
            self.send_message(finish_room_disabled_message)
        elif self.__selected_room.visited_by_color_blind or self.__selected_room.visited_by_shape_blind:
            finish_checking_room_after_disabled_message = \
                generate_finish_disabled_door_message(self.__selected_room, self.agent_id,
                                                      self.__teammate_ids)
            self.send_message(
                finish_checking_room_after_disabled_message)
        elif self.__shape_blind or self.__color_blind:
            finish_room_disabled_message = generate_disabled_door_message(state,
                                                                          self.__selected_room,
                                                                          self.__color_blind,
                                                                          self.__shape_blind,
                                                                          self.agent_id,
                                                                          self.__teammate_ids)
            self.send_message(finish_room_disabled_message)

    def grab_shape_command(self, shape: Shape, goal: GoalBlock):
        # print("grab")

        pickeup_object_message = generate_pickeup_object_message(
            shape, goal, self.agent_id, self.__teammate_ids)
        self.send_message(pickeup_object_message)

        self.__inventory.append((shape, goal))
        self.__located_shapes.remove(shape)
        self.__goal_blocks_needed.remove(goal)
        if len(self.__goal_blocks_needed) == 0:
            self.__fsm_state = FSMState.DROPPING

        return GrabObject.__name__, {'object_id': shape.block_id}

    def drop(self, state):
        # print("drop")
        items_in_inventory = check_if_items_in_inventory(state, self.agent_id)
        if items_in_inventory:
            self.__waypoints = []
            drop_off_location = get_waypoint_finish(state)
            self.__waypoints.append(drop_off_location)
            self.plan_path(drop_off_location)
            self.__fsm_state = FSMState.FINISH
            return self.finish(state)
        else:
            self.plan_path((1, 1))
            self.__fsm_state = FSMState.STOP
            return self.get_next_movement()

    def finish(self, state):
        # print("finish")

        if len(self.__inventory) == 0:
            self.plan_path((1, 1))
            self.__fsm_state = FSMState.STOP
            return self.get_next_movement()

        if not self.__agent_location == self.__waypoints[0]:
            return self.get_next_movement()

        self.__goal_blocks = order_goal_blocks(self.__goal_blocks)
        state_dict = state.as_dict()

        blocks_at_drop_off = self.find_blocks_at_drop_off(state_dict)

        for block_at_drop_off in blocks_at_drop_off:
            for goal_block in self.__goal_blocks:
                if block_at_drop_off['location'] == goal_block.location:
                    self.__goal_blocks.remove(goal_block)

        if len(self.__goal_blocks) == 0:
            self.plan_path((1, 1))
            self.__fsm_state = FSMState.STOP
            return self.get_next_movement()

        for inventory_tuple in self.__inventory:
            if inventory_tuple[1].id == self.__goal_blocks[0].id:
                if not self.__agent_location == self.__goal_blocks[0].location:
                    self.__waypoints = [self.__goal_blocks[0].location]
                    self.plan_path(self.__waypoints[0])
                    return self.get_next_movement()
                block_id = inventory_tuple[0].block_id
                self.__inventory.remove(inventory_tuple)
                return DropObject.__name__, {'object_id': block_id}

        return (None, {})

    def find_blocks_at_drop_off(self, state_dict):
        objects_at_drop_off = []
        for key in state_dict:
            if 'location' in state_dict[key]:
                object_in_world = state_dict[key]
                for goal_block in self.__goal_blocks:
                    if object_in_world['location'] == goal_block.location:
                        if key.startswith('Block_in_room'):
                            objects_at_drop_off.append(state_dict[key])
        return objects_at_drop_off

    def stop(self, state):
        # print("stop")
        return self.get_next_movement()

    def plan_path(self, target_loc=(int, int)):
        self.navigator.reset_full()
        self.navigator.add_waypoints([target_loc])

    def get_next_movement(self):
        action = self.navigator.get_move_action(self.state_tracker)
        if action is None:
            action = random.choice(self._moves)
        return action, {}

    def get_first_room_index(self):
        selected_room_index = 0
        if len(self.__room_infos) >= 2:
            random_selection = random.uniform(0, 1)
            room_chance = max(1 / len(self.__room_infos), 1 / 3)
            if random_selection < room_chance:
                selected_room_index = 0
            elif random_selection < (room_chance * 2):
                selected_room_index = 1
            else:
                selected_room_index = 2
        return selected_room_index

    def set_next_waypoints_room(self, state, selected_room_index):
        self.__waypoints.append(
            self.__room_infos[selected_room_index].porch_location)
        room_waypoints = calculate_room_traversal_waypoints(
            state, self.__room_infos[selected_room_index].room_name)
        for room_waypoint in room_waypoints:
            self.__waypoints.append(room_waypoint)

        self.__selected_room = self.__room_infos[selected_room_index]
        del (self.__room_infos[selected_room_index])

    # updates the global visited objects list with all new objects that our agent sees
    def update_visited_objects(self, state: State):
        shapes = get_close_objects(
            state, self.__shape_blind, self.__color_blind)
        for shape in shapes:
            if shape not in self.__located_shapes:
                self.__located_shapes.append(shape)
            else:
                for located_shape in self.__located_shapes:
                    if located_shape.block_id == shape.block_id:
                        if located_shape.color is None:
                            located_shape.color = shape.color
                        if located_shape.shape is None:
                            located_shape.shape = shape.shape
