"""
This library allows you to quickly and easily use the SendGrid Web API v3 via
Python.

For more information on this library, see the README on Github.
    http://github.com/sendgrid/sendgrid-python
For more information on the SendGrid v3 API, see the v3 docs:
    http://sendgrid.com/docs/API_Reference/api_v3.html
For the user guide, code examples, and more, visit the main docs page:
    http://sendgrid.com/docs/index.html

Available subpackages
---------------------
helpers
    Modules to help with common tasks.
"""

from .version import __version__  # noqa
# v3 API
from .sendgrid import SendGridAPIClient  # noqa
from .helpers.mail import Email  # noqa
