class BCCSettings(object):
    """Settings object for automatic BCC.

    This allows you to have a blind carbon copy automatically sent to the
    specified email address for every email that is sent.
    """

    def __init__(self, enable=None, email=None):
        """Create a BCCSettings.

        :param enable: Whether this BCCSettings is applied to sent emails.
        :type enable: boolean, optional
        :param email: Who should be BCCed.
        :type email: Email, optional
        """
        self.enable = enable
        self.email = email

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
    def email(self):
        """The email address that you would like to receive the BCC.

        :rtype: Email
        """
        return self._email

    @email.setter
    def email(self, value):
        self._email = value

    def get(self):
        """
        Get a JSON-ready representation of this BCCSettings.

        :returns: This BCCSettings, ready for use in a request body.
        :rtype: dict
        """
        bcc_settings = {}
        if self.enable is not None:
            bcc_settings["enable"] = self.enable

        if self.email is not None:
            email = self.email.get()
            bcc_settings["email"] = email["email"]
        return bcc_settings
