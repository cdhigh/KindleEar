class CustomArg(object):
    """Values that will be carried along with the email and its activity data.

    Substitutions will not be made on custom arguments, so any string entered
    into this parameter will be assumed to be the custom argument that you
    would like to be used. Top-level CustomArgs may be overridden by ones in a
    Personalization. May not exceed 10,000 bytes.
    """

    def __init__(self, key=None, value=None):
        """Create a CustomArg with the given key and value."""
        self.key = key
        self.value = value

    @property
    def key(self):
        """Key for this CustomArg.

        :rtype: string
        """
        return self._key

    @key.setter
    def key(self, value):
        self._key = value

    @property
    def value(self):
        """Value of this CustomArg."""
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def get(self):
        """
        Get a JSON-ready representation of this CustomArg.

        :returns: This CustomArg, ready for use in a request body.
        :rtype: dict
        """
        custom_arg = {}
        if self.key is not None and self.value is not None:
            custom_arg[self.key] = self.value
        return custom_arg
