from typing import List, Dict
import ast

KEYS_TO_TYPE_MAPPING: Dict = {
    'obj_id': str,
    'location': tuple,
    'carried_by': list,
    'colour': str,
    'shape': int
}


class Block:
    def __init__(self,
                 obj_id: str,
                 location: tuple,
                 carried_by: List[str],
                 colour: str,
                 shape: int):
        self.obj_id = obj_id
        self.location = location
        self.carried_by = carried_by
        self.colour = colour
        self.shape = shape

    def __str__(self):
        return "{{" \
               "'obj_id': '{0}'," \
               "'location': {1}," \
               "'carried_by': {2}," \
               "'colour': '{3}'," \
               "'shape': {4}" \
               "}}" \
            .format(self.obj_id,
                    self.location,
                    self.carried_by,
                    self.colour,
                    self.shape)

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
        # if self.get_obj_id() != other.get_obj_id() or \
        #         self.get_location() != other.get_location() or \
        #         self.get_carried_by() != other.get_carried_by():
        if self.get_obj_id() != other.get_obj_id():

            print(
                "VALUE ERROR: " + self.__str__() + " AND " + other.__str__() + " DOESN'T HAVE EQUAL NECESSARY FIELD "
                                                                               "VALUES!")
            return None

        else:
            block_ret = Block(self.obj_id, other.get_location(), other.get_carried_by(), None, None)
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
        return hash((self.obj_id, self.location, self.colour, self.shape))

    def get_colour(self) -> str:
        return self.colour

    def get_shape(self) -> int:
        return self.shape

    def get_location(self):
        return self.location


    def get_obj_id(self):
        return self.obj_id

    def get_carried_by(self):
        return self.carried_by
    
    def set_location(self, loc):
        self.location = loc

    def set_carried_by(self, val):
        self.carried_by = val

    def set_colour(self, val):
        self.colour = val

    def set_shape(self, val):
        self.shape = val

    @staticmethod
    def str_to_block(block_str: str):
        """
        :param block_str: the string representation of the block object
        :return: Block object after parsing block_str.
                 None if one of the values of block_str is None OR if given block_str is not a valid Block representation
        """
        try:
            # convert string to dict. the string must be a string representation of object format
            msg_obj = ast.literal_eval(block_str)
            msg_vals = list(msg_obj.values())[0]
            msg_key = list(msg_obj)[0].lower()

            # checking whether key is not none
            if 'block_in_room' not in msg_key and 'collect_block' not in msg_key:
                err_msg = f"ERROR: MSG KEY (obj_id) {msg_key} DOES NOT CONTAIN EXPECTED Block_in_room_*_*** FORMAT!"
                print(err_msg)
                raise Exception

            # check whether the converted object has the expected keys of a Block
            if msg_vals.keys() != KEYS_TO_TYPE_MAPPING.keys():
                err_msg = "ERROR: " + block_str + " DOES NOT CONTAIN EXPECTED KEYS FOR BLOCK!"
                print(err_msg)
                raise Exception

            # check whether the necessary fields of a Block have values in expected type
            vals = {}
            for (k, t) in KEYS_TO_TYPE_MAPPING.items():
                val = msg_vals.get(k, None)
                if k == 'colour' or k == 'shape':
                    vals[k] = val
                else:
                    if val is not None and isinstance(val, t):
                        vals[k] = val
                    else:
                        err_msg = "ERROR: " + block_str + " HAS NONE VALUES! BLOCK OBJECT MUST NOT HAVE A NONE VALUE!"
                        print(err_msg)
                        raise Exception

            return Block(**vals)

        except:
            print(f'INVALID BLOCK REPRESENTATION: {block_str} -> Returning None ...')
            return None
