class Category(object):
    """A category name for this message."""

    def __init__(self, name=None):
        """Create a Category.

        :param name: The name of this category
        :type name: string, optional
        """
        self.name = name

    @property
    def name(self):
        """The name of this Category. Must be less than 255 characters.

        :rtype: string
        """
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def get(self):
        """
        Get a JSON-ready representation of this Category.

        :returns: This Category, ready for use in a request body.
        :rtype: string
        """
        return self.name
