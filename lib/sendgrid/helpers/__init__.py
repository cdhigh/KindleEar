"""v3/mail/send response body builder

Builder for assembling emails to be sent with the v3 SendGrid API.

Usage example:
    def build_hello_email():
        to_email = from_email = Email("test@example.com")
        subject = "Hello World from the SendGrid Python Library"
        content = Content("text/plain", "some text here")
        mail = Mail(from_email, subject, to_email, content)
        mail.personalizations[0].add_to(Email("test2@example.com"))
        return mail.get()  # assembled request body

For more usage examples, see
https://github.com/sendgrid/sendgrid-python/tree/master/examples/helpers/mail

For more information on the v3 API, see
https://sendgrid.com/docs/API_Reference/api_v3.html
"""
