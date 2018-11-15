class TrackingSettings(object):
    """Settings to track how recipients interact with your email."""

    def __init__(self):
        """Create an empty TrackingSettings."""
        self._click_tracking = None
        self._open_tracking = None
        self._subscription_tracking = None
        self._ganalytics = None

    @property
    def click_tracking(self):
        """Allows you to track whether a recipient clicked a link in your email.

        :rtype: ClickTracking
        """
        return self._click_tracking

    @click_tracking.setter
    def click_tracking(self, value):
        self._click_tracking = value

    @property
    def open_tracking(self):
        """Allows you to track whether a recipient opened your email.

        :rtype: OpenTracking
        """
        return self._open_tracking

    @open_tracking.setter
    def open_tracking(self, value):
        self._open_tracking = value

    @property
    def subscription_tracking(self):
        """Settings for the subscription management link.

        :rtype: SubscriptionTracking
        """
        return self._subscription_tracking

    @subscription_tracking.setter
    def subscription_tracking(self, value):
        self._subscription_tracking = value

    @property
    def ganalytics(self):
        """Settings for Google Analytics.

        :rtype: Ganalytics
        """
        return self._ganalytics

    @ganalytics.setter
    def ganalytics(self, value):
        self._ganalytics = value

    def get(self):
        """
        Get a JSON-ready representation of this TrackingSettings.

        :returns: This TrackingSettings, ready for use in a request body.
        :rtype: dict
        """
        tracking_settings = {}
        if self.click_tracking is not None:
            tracking_settings["click_tracking"] = self.click_tracking.get()
        if self.open_tracking is not None:
            tracking_settings["open_tracking"] = self.open_tracking.get()
        if self.subscription_tracking is not None:
            tracking_settings[
                "subscription_tracking"] = self.subscription_tracking.get()
        if self.ganalytics is not None:
            tracking_settings["ganalytics"] = self.ganalytics.get()
        return tracking_settings
