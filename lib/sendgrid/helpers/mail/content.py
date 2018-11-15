from .validators import ValidateAPIKey

class Content(object):
    """Content to be included in your email.

    You must specify at least one mime type in the Contents of your email.
    """

    def __init__(self, type_=None, value=None):
        """Create a Content with the specified MIME type and value.

        :param type_: MIME type of this Content (e.g. "text/plain").
        :type type_: string, optional
        :param value: The actual content.
        :type value: string, optional
        """
        self._type = None
        self._value = None
        self._validator = ValidateAPIKey()

        if type_ is not None:
            self.type = type_

        if value is not None:
            self.value = value

    @property
    def type(self):
        """The MIME type of the content you are including in your email.

        For example, "text/plain" or "text/html".

        :rtype: string
        """
        return self._type

    @type.setter
    def type(self, value):
        self._type = value

    @property
    def value(self):
        """The actual content (of the specified mime type).

        :rtype: string
        """
        return self._value

    @value.setter
    def value(self, value):
        self._validator.validate_message_dict(value)
        self._value = value

    def get(self):
        """
        Get a JSON-ready representation of this Content.

        :returns: This Content, ready for use in a request body.
        :rtype: dict
        """
        content = {}
        if self.type is not None:
            content["type"] = self.type

        if self.value is not None:
            content["value"] = self.value
        return content
