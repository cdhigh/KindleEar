class SpamCheck(object):
    """This allows you to test the content of your email for spam."""

    def __init__(self, enable=None, threshold=None, post_to_url=None):
        """Create a SpamCheck to test the content of your email for spam.

        :param enable: If this setting is applied.
        :type enable: boolean, optional
        :param threshold: Spam qualification threshold, from 1 to 10 (strict).
        :type threshold: int, optional
        :param post_to_url: Inbound Parse URL to send a copy of your email.
        :type post_to_url: string, optional
        """
        self.enable = enable
        self.threshold = threshold
        self.post_to_url = post_to_url

    @property
    def enable(self):
        """Indicates if this setting is enabled.

        :rtype: boolean
        """
        return self._enable

    @enable.setter
    def enable(self, value):
        self._enable = value

    @property
    def threshold(self):
        """Threshold used to determine if your content qualifies as spam.

        On a scale from 1 to 10, with 10 being most strict, or most likely to
        be considered as spam.
        :rtype: int
        """
        return self._threshold

    @threshold.setter
    def threshold(self, value):
        self._threshold = value

    @property
    def post_to_url(self):
        """An Inbound Parse URL to send a copy of your email.

        If defined, a copy of your email and its spam report will be sent here.
        :rtype: string
        """
        return self._post_to_url

    @post_to_url.setter
    def post_to_url(self, value):
        self._post_to_url = value

    def get(self):
        """
        Get a JSON-ready representation of this SpamCheck.

        :returns: This SpamCheck, ready for use in a request body.
        :rtype: dict
        """
        spam_check = {}
        if self.enable is not None:
            spam_check["enable"] = self.enable

        if self.threshold is not None:
            spam_check["threshold"] = self.threshold

        if self.post_to_url is not None:
            spam_check["post_to_url"] = self.post_to_url
        return spam_check
