class Section(object):
    """A block section of code to be used as a substitution."""

    def __init__(self, key=None, value=None):
        """Create a section with the given key and value."""
        self.key = key
        self.value = value

    @property
    def key(self):
        return self._key

    @key.setter
    def key(self, value):
        self._key = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def get(self):
        """
        Get a JSON-ready representation of this Section.

        :returns: This Section, ready for use in a request body.
        :rtype: dict
        """
        section = {}
        if self.key is not None and self.value is not None:
            section[self.key] = self.value
        return section
