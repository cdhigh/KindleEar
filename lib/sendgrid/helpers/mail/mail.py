"""v3/mail/send response body builder"""
from .personalization import Personalization
from .header import Header
from .email import Email


class Mail(object):
    """A request to be sent with the SendGrid v3 Mail Send API (v3/mail/send).

    Use get() to get the request body.
    """
    def __init__(self,
                 from_email=None,
                 subject=None,
                 to_email=None,
                 content=None):
        """Create a Mail object.

        If any parameters are not supplied, they must be set after initialization.
        :param from_email: Email address to send from.
        :type from_email: Email, optional
        :param subject: Subject line of emails.
        :type subject: string, optional
        :param to_email: Email address to send to.
        :type to_email: Email, optional
        :param content: Content of the message.
        :type content: Content, optional
        """
        self._from_email = None
        self._subject = None
        self._template_id = None
        self._send_at = None
        self._batch_id = None
        self._asm = None
        self._ip_pool_name = None
        self._mail_settings = None
        self._tracking_settings = None
        self._reply_to = None
        self._personalizations = []
        self._contents = []
        self._attachments = []
        self._sections = []
        self._headers = []
        self._categories = []
        self._custom_args = []

        if from_email:
            self.from_email = from_email

        if subject:
            self.subject = subject

        if to_email:
            personalization = Personalization()
            personalization.add_to(to_email)
            self.add_personalization(personalization)

        if content:
            self.add_content(content)

    def __str__(self):
        """Get a JSON representation of this Mail request.

        :rtype: string
        """
        return str(self.get())

    def get(self):
        """Get a response body for this Mail.

        :rtype: dict
        """
        mail = {}

        if self.from_email is not None:
            mail["from"] = self.from_email.get()

        if self.subject is not None:
            mail["subject"] = self.subject

        if self.personalizations:
            mail["personalizations"] = [
                personalization.get()
                for personalization in self.personalizations
            ]

        if self.contents:
            mail["content"] = [ob.get() for ob in self.contents]

        if self.attachments:
            mail["attachments"] = [ob.get() for ob in self.attachments]

        if self.template_id is not None:
            mail["template_id"] = self.template_id

        if self.sections:
            sections = {}
            for key in self.sections:
                sections.update(key.get())
            mail["sections"] = sections

        if self.headers:
            headers = {}
            for key in self.headers:
                headers.update(key.get())
            mail["headers"] = headers

        if self.categories:
            mail["categories"] = [category.get() for category in
                                  self.categories]

        if self.custom_args:
            custom_args = {}
            for key in self.custom_args:
                custom_args.update(key.get())
            mail["custom_args"] = custom_args

        if self.send_at is not None:
            mail["send_at"] = self.send_at

        if self.batch_id is not None:
            mail["batch_id"] = self.batch_id

        if self.asm is not None:
            mail["asm"] = self.asm.get()

        if self.ip_pool_name is not None:
            mail["ip_pool_name"] = self.ip_pool_name

        if self.mail_settings is not None:
            mail["mail_settings"] = self.mail_settings.get()

        if self.tracking_settings is not None:
            mail["tracking_settings"] = self.tracking_settings.get()

        if self.reply_to is not None:
            mail["reply_to"] = self.reply_to.get()

        return mail

    @property
    def from_email(self):
        """The email from which this Mail will be sent.

        :rtype: string
        """
        return self._from_email

    @from_email.setter
    def from_email(self, value):
        if isinstance(value, str):
            value = Email(value)
        self._from_email = value

    @property
    def subject(self):
        """The global, or "message level", subject of this Mail.

        This may be overridden by personalizations[x].subject.
        :rtype: string
        """
        return self._subject

    @subject.setter
    def subject(self, value):
        self._subject = value

    @property
    def template_id(self):
        """The id of a template that you would like to use.

        If you use a template that contains a subject and content (either text
        or html), you do not need to specify those at the personalizations nor
        message level.

        :rtype: int
        """

        return self._template_id

    @template_id.setter
    def template_id(self, value):
        self._template_id = value

    @property
    def send_at(self):
        """A unix timestamp allowing you to specify when you want your email to
        be delivered. This may be overridden by the personalizations[x].send_at
        parameter. Scheduling more than 72 hours in advance is forbidden.

        :rtype: int
        """
        return self._send_at

    @send_at.setter
    def send_at(self, value):
        self._send_at = value

    @property
    def batch_id(self):
        """An ID for this batch of emails.

        This represents a batch of emails sent at the same time. Including a
        batch_id in your request allows you include this email in that batch,
        and also enables you to cancel or pause the delivery of that batch.
        For more information, see https://sendgrid.com/docs/API_Reference/Web_API_v3/cancel_schedule_send.html

        :rtype: int
        """
        return self._batch_id

    @batch_id.setter
    def batch_id(self, value):
        self._batch_id = value

    @property
    def asm(self):
        """The ASM for this Mail.

        :rtype: ASM
        """
        return self._asm

    @asm.setter
    def asm(self, value):
        self._asm = value

    @property
    def mail_settings(self):
        """The MailSettings for this Mail.

        :rtype: MailSettings
        """
        return self._mail_settings

    @mail_settings.setter
    def mail_settings(self, value):
        self._mail_settings = value

    @property
    def tracking_settings(self):
        """The TrackingSettings for this Mail.

        :rtype: TrackingSettings
        """
        return self._tracking_settings

    @tracking_settings.setter
    def tracking_settings(self, value):
        self._tracking_settings = value

    @property
    def ip_pool_name(self):
        """The IP Pool that you would like to send this Mail email from.

        :rtype: string
        """
        return self._ip_pool_name

    @ip_pool_name.setter
    def ip_pool_name(self, value):
        self._ip_pool_name = value

    @property
    def reply_to(self):
        """The email address to use in the Reply-To header.

        :rtype: Email
        """
        return self._reply_to

    @reply_to.setter
    def reply_to(self, value):
        self._reply_to = value

    @property
    def personalizations(self):
        """The Personalizations applied to this Mail.

        Each object within personalizations can be thought of as an envelope -
        it defines who should receive an individual message and how that
        message should be handled. A maximum of 1000 personalizations can be
        included.

        :rtype: list
        """
        return self._personalizations

    def add_personalization(self, personalizations):
        """Add a new Personalization to this Mail.

        :type personalizations: Personalization
        """
        self._personalizations.append(personalizations)

    @property
    def contents(self):
        """The Contents of this Mail. Must include at least one MIME type.

        :rtype: list(Content)
        """
        return self._contents

    def add_content(self, content):
        """Add a new Content to this Mail.  Usually the plaintext or HTML
        message contents.

        :type content: Content
        """
        if self._contents is None:
            self._contents = []

        # Text content should be before HTML content
        if content._type == "text/plain":
            self._contents.insert(0, content)
        else:
            self._contents.append(content)

    @property
    def attachments(self):
        """The attachments included with this Mail.

        :returns: List of Attachment objects.
        :rtype: list(Attachment)
        """
        return self._attachments

    def add_attachment(self, attachment):
        """Add an Attachment to this Mail.

        :type attachment: Attachment
        """
        self._attachments.append(attachment)

    @property
    def sections(self):
        """The sections included with this Mail.

        :returns: List of Section objects.
        :rtype: list(Section)
        """
        return self._sections

    def add_section(self, section):
        """Add a Section to this Mail.

        :type section: Section
        """
        self._sections.append(section)

    @property
    def headers(self):
        """The Headers included with this Mail.

        :returns: List of Header objects.
        :rtype: list(Header)
        """
        return self._headers

    def add_header(self, header):
        """Add a Header to this Mail.

        The header provided can be a Header or a dictionary with a single
        key-value pair.
        :type header: object
        """
        if isinstance(header, dict):
            (k, v) = list(header.items())[0]
            self._headers.append(Header(k, v))
        else:
            self._headers.append(header)

    @property
    def categories(self):
        """The Categories applied to this Mail.  Must not exceed 10 items

        :rtype: list(Category)
        """
        return self._categories

    def add_category(self, category):
        """Add a Category to this Mail.

        :type category: Category
        """
        self._categories.append(category)

    @property
    def custom_args(self):
        """The CustomArgs attached to this Mail.

        Must not exceed 10,000 characters.
        :rtype: list(CustomArg)
        """
        return self._custom_args

    def add_custom_arg(self, custom_arg):
        if self._custom_args is None:
            self._custom_args = []
        self._custom_args.append(custom_arg)
