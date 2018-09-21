################################################################
# Various types of extensible SendGrid related exceptions
################################################################

class SendGridException(Exception):
    """Wrapper/default SendGrid-related exception"""
    pass


class APIKeyIncludedException(SendGridException):
    """Exception raised for when SendGrid API Key included in message text
        Attributes:
            expression -- input expression in which the error occurred
            message -- explanation of the error
    """

    def __init__(self, 
                 expression="Email body", 
                 message="SendGrid API Key detected"):
        self.expression = expression
        self.message = message

