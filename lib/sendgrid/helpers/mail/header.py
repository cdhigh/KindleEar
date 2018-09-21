class Header(object):
    """A header to specify specific handling instructions for your email.

    If the name or value contain Unicode characters, they must be properly
    encoded. You may not overwrite the following reserved headers:
    x-sg-id, x-sg-eid, received, dkim-signature, Content-Type,
    Content-Transfer-Encoding, To, From, Subject, Reply-To, CC, BCC
    """

    def __init__(self, key=None, value=None):
        """Create a Header.

        :param key: The name of the header (e.g. "Date")
        :type key: string, optional
        :param value: The header's value (e.g. "2013-02-27 1:23:45 PM PDT")
        :type value: string, optional
        """
        self._key = None
        self._value = None

        if key is not None:
            self.key = key
        if value is not None:
            self.value = value

    @property
    def key(self):
        """The name of the header.

        :rtype: string
        """
        return self._key

    @key.setter
    def key(self, value):
        self._key = value

    @property
    def value(self):
        """The value of the header.

        :rtype: string
        """
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def get(self):
        """
        Get a JSON-ready representation of this Header.

        :returns: This Header, ready for use in a request body.
        :rtype: dict
        """
        header = {}
        if self.key is not None and self.value is not None:
            header[self.key] = self.value
        return header
