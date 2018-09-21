class ASM(object):
    """An object specifying unsubscribe behavior."""

    def __init__(self, group_id=None, groups_to_display=None):
        """Create an ASM with the given group_id and groups_to_display.

        :param group_id: ID of an unsubscribe group
        :type group_id: int, optional
        :param groups_to_display: Unsubscribe groups to display
        :type groups_to_display: list(int), optional
        """
        self._group_id = None
        self._groups_to_display = None

        if group_id is not None:
            self.group_id = group_id

        if groups_to_display is not None:
            self.groups_to_display = groups_to_display

    @property
    def group_id(self):
        """The unsubscribe group to associate with this email.

        :rtype: integer
        """
        return self._group_id

    @group_id.setter
    def group_id(self, value):
        self._group_id = value

    @property
    def groups_to_display(self):
        """The unsubscribe groups that you would like to be displayed on the
        unsubscribe preferences page. Max of 25 groups.

        :rtype: list(int)
        """
        return self._groups_to_display

    @groups_to_display.setter
    def groups_to_display(self, value):
        if value is not None and len(value) > 25:
            raise ValueError("New groups_to_display exceeds max length of 25.")
        self._groups_to_display = value

    def get(self):
        """
        Get a JSON-ready representation of this ASM.

        :returns: This ASM, ready for use in a request body.
        :rtype: dict
        """
        asm = {}
        if self.group_id is not None:
            asm["group_id"] = self.group_id

        if self.groups_to_display is not None:
            asm["groups_to_display"] = self.groups_to_display
        return asm
