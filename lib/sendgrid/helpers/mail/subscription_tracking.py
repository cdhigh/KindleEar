class SubscriptionTracking(object):
    """Allows you to insert a subscription management link at the bottom of the
    text and html bodies of your email. If you would like to specify the
    location of the link within your email, you may use the substitution_tag.
    """

    def __init__(self, enable=None, text=None, html=None, substitution_tag=None):
        """Create a SubscriptionTracking to customize subscription management.

        :param enable: Whether this setting is enabled.
        :type enable: boolean, optional
        :param text: Text to be appended to the email with the link as "<% %>".
        :type text: string, optional
        :param html: HTML to be appended to the email with the link as "<% %>".
        :type html: string, optional
        :param substitution_tag: Tag replaced with URL. Overrides text, html params.
        :type substitution_tag: string, optional
        """
        self.enable = enable
        self.text = text
        self.html = html
        self.substitution_tag = substitution_tag

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
    def text(self):
        """Text to be appended to the email, with the subscription tracking
        link. You may control where the link is by using the tag <% %>
        :rtype: string
        """
        return self._text

    @text.setter
    def text(self, value):
        self._text = value

    @property
    def html(self):
        """HTML to be appended to the email, with the subscription tracking
        link. You may control where the link is by using the tag <% %>
        :rtype: string
        """
        return self._html

    @html.setter
    def html(self, value):
        self._html = value

    @property
    def substitution_tag(self):
        """"A tag that will be replaced with the unsubscribe URL. for example:
        [unsubscribe_url]. If this parameter is used, it will override both the
        `text` and `html` parameters. The URL of the link will be placed at the
        substitution tag's location, with no additional formatting.
        :rtype: string
        """
        return self._substitution_tag

    @substitution_tag.setter
    def substitution_tag(self, value):
        self._substitution_tag = value

    def get(self):
        """
        Get a JSON-ready representation of this SubscriptionTracking.

        :returns: This SubscriptionTracking, ready for use in a request body.
        :rtype: dict
        """
        subscription_tracking = {}
        if self.enable is not None:
            subscription_tracking["enable"] = self.enable

        if self.text is not None:
            subscription_tracking["text"] = self.text

        if self.html is not None:
            subscription_tracking["html"] = self.html

        if self.substitution_tag is not None:
            subscription_tracking["substitution_tag"] = self.substitution_tag
        return subscription_tracking
