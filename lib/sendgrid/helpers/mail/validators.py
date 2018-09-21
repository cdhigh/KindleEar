from .exceptions import APIKeyIncludedException
################################################################
# Various types of Validators
################################################################

class ValidateAPIKey(object):
    """Validates content to ensure SendGrid API key is not present"""

    regexes = None

    def __init__(self, regex_strings=None, use_default=True):
        """Constructor
        Args:
            regex_strings (list<str>): list of regex strings
            use_default (bool): Whether or not to include default regex
        """

        import re
        self.regexes = set()

        # Compile the regex strings into patterns, add them to our set
        if regex_strings is not None:
            for regex_string in regex_strings:
                self.regexes.add(re.compile(regex_string))

        if use_default:
            default_regex_string = 'SG\.[0-9a-zA-Z]+\.[0-9a-zA-Z]+'
            self.regexes.add(re.compile(default_regex_string))


    def validate_message_dict(self, request_body):
        """With the JSON dict that will be sent to SendGrid's API, 
            check the content for SendGrid API keys - throw exception if found
        Args:
            request_body (:obj:`dict`): message parameter that is
                                            an argument to: mail.send.post()
        Raises:
            APIKeyIncludedException: If any content in request_body matches regex
        """

        # Handle string in edge-case
        if isinstance(request_body, str):
            self.validate_message_text(request_body)

        # Default param
        elif isinstance(request_body, dict):
            
            contents = request_body.get("content", list())
            
            for content in contents:
                if content is not None:
                    if (content.get("type") == "text/html" or
                            isinstance(content.get("value"), str)):
                        message_text = content.get("value", "")
                        self.validate_message_text(message_text)

                        
    def validate_message_text(self, message_string):
        """With a message string, check to see if it contains a SendGrid API Key
            If a key is found, throw an exception
        Args:
            message_string (str): message that will be sent
        Raises:
            APIKeyIncludedException: If message_string matches a regex string
        """

        if isinstance(message_string, str):
            for regex in self.regexes:
                if regex.match(message_string) is not None:
                    raise APIKeyIncludedException()

