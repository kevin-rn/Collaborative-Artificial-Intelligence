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
