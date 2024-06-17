#!/usr/bin/env python3
# -*- coding:utf-8 -*-
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Defines various abstract base classes that can be subclassed to create powerful news fetching recipes.
'''
__docformat__ = "restructuredtext en"


import io, os, re, sys, time, datetime, traceback, base64
from collections import defaultdict, namedtuple
from urllib.parse import urlparse, urlsplit, quote, urljoin
from urllib.error import HTTPError, URLError
from calibre import __appname__, as_unicode, force_unicode, iswindows, preferred_encoding, strftime
from calibre.ebooks.BeautifulSoup import BeautifulSoup, CData, NavigableString, Tag
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.ebooks.metadata.toc import TOC
from calibre.ptempfile import PersistentTemporaryFile, PersistentTemporaryDirectory
from calibre.utils.img import save_cover_data_to
from calibre.utils.date import now as nowf
from calibre.utils.localization import canonicalize_lang, ngettext
from calibre.utils.threadpool import NoResultsPending, ThreadPool, WorkRequest
from calibre.web import Recipe
from calibre.web.feeds import Feed, Article, feed_from_xml, feeds_from_index, templates, feed_from_json
from calibre.web.fetch.simple import AbortArticle, RecursiveFetcher
from calibre.web.fetch.utils import prepare_masthead_image
from polyglot.builtins import string_or_bytes
from lxml.html import document_fromstring, fragment_fromstring, tostring
import readability
from simpleextract import simple_extract
from urlopener import UrlOpener
from requests_file import LocalFileAdapter
from filesystem_dict import FsDictStub
from application.back_end.db_models import LastDelivered
from application.utils import loc_exc_pos

MASTHEAD_SIZE = (600, 60)
DEFAULT_MASTHEAD_IMAGE = 'mastheadImage.gif'
COVER_SIZE = (832, 1280)

def classes(classes):
    q = frozenset(classes.split(' '))
    return dict(attrs={
        'class': lambda x: x and frozenset(x.split()).intersection(q)})

def prefixed_classes(classes):
    q = frozenset(classes.split(' '))

    def matcher(x):
        if x:
            for candidate in frozenset(x.split()):
                for x in q:
                    if candidate.startswith(x):
                        return True
        return False
    return {'attrs': {'class': matcher}}

class LoginFailed(ValueError):
    pass

class DownloadDenied(ValueError):
    pass

class Web2diskOptions:
    def __init__(self):
        self.keep_only_tags = []
        self.remove_tags = []
        self.preprocess_regexps = []
        self.skip_ad_pages = lambda soup: None
        self.preprocess_html = lambda soup: soup
        self.remove_tags_after = None
        self.remove_tags_before = None
        self.is_link_wanted = None
        self.compress_news_images = False
        self.compress_news_images_max_size = None
        self.compress_news_images_auto_size = 16
        self.scale_news_images = None
        self.filter_regexps = []
        self.match_regexps = []
        self.no_stylesheets = False
        self.verbose = False
        self.delay = 0
        self.timeout = 60
        self.recursions = 0
        self.encoding = None
        self.postprocess_html = None
        self.preprocess_image = None
        self.preprocess_raw_html = None
        self.get_delay = None
        self.max_files = None
        self.keep_images = True
        self.keep_svg = False


#每篇文章的下载任务参数
#url: 要下载的url
#art_dir: 下载的内容要保存的目录，包括html文本和里面的图像文件
#f_idx: Feed索引号
#a_idx: 文章在Feed里面的索引号
#feed_len: Feed总数
#article: calibre.web.feeds.__init__.Article 实例
JobInfo = namedtuple('JobInfo', 'url art_dir f_idx a_idx feed_len article')

class BasicNewsRecipe(Recipe):
    #: The title to use for the e-book
    title                  = 'Unknown News Source'

    #: A couple of lines that describe the content this recipe downloads.
    #: This will be used primarily in a GUI that presents a list of recipes.
    description = ''

    #: The author of this recipe
    __author__             = "KindleEar"

    #: Minimum calibre version needed to use this recipe
    requires_version = (0, 6, 0)

    #: The language that the news is in. Must be an ISO-639 code either
    #: two or three characters long
    language               = 'und'

    #: Maximum number of articles to download from each feed. This is primarily
    #: useful for feeds that don't have article dates. For most feeds, you should
    #: use :attr:`BasicNewsRecipe.oldest_article`
    max_articles_per_feed  = 30

    #: Oldest article to download from this news source. In days.
    oldest_article         = 7

    #: Number of levels of links to follow on article webpages
    recursions             = 0

    #: The default delay between consecutive downloads in seconds. The argument may be a
    #: floating point number to indicate a more precise time. See :meth:`get_url_specific_delay`
    #: to implement per URL delays.
    delay                  = 0

    #: Publication type
    #: Set to newspaper, magazine or blog. If set to None, no publication type
    #: metadata will be written to the opf file.
    publication_type = 'unknown'

    #: Number of simultaneous downloads. Set to 1 if the server is picky.
    #: Automatically reduced to 1 if :attr:`BasicNewsRecipe.delay` > 0
    simultaneous_downloads = 5

    #: Timeout for fetching files from server in seconds
    timeout                = 60

    #: The format string for the date shown on the first page.
    #: By default: Day_Name, Day_Number Month_Name Year
    timefmt                = ' [%a, %d %b %Y]'

    #: List of feeds to download.
    #: Can be either ``[url1, url2, ...]`` or ``[('title1', url1), ('title2', url2),...]``
    feeds = None

    #: Max number of characters in the short description
    summary_length         = 300

    #: Convenient flag to disable loading of stylesheets for websites
    #: that have overly complex stylesheets unsuitable for conversion
    #: to e-book formats.
    #: If True stylesheets are not downloaded and processed
    no_stylesheets         = True

    #: Convenient flag to strip all JavaScript tags from the downloaded HTML
    remove_javascript      = True

    #: If True the GUI will ask the user for a username and password
    #: to use while downloading.
    #: If set to "optional" the use of a username and password becomes optional
    needs_subscription     = False

    #: If True the navigation bar is center aligned, otherwise it is left aligned
    center_navbar = True

    #: Specify an override encoding for sites that have an incorrect
    #: charset specification. The most common being specifying ``latin1`` and
    #: using ``cp1252``. If None, try to detect the encoding. If it is a
    #: callable, the callable is called with two arguments: The recipe object
    #: and the source to be decoded. It must return the decoded source.
    encoding               = None

    #: Normally we try to guess if a feed has full articles embedded in it
    #: based on the length of the embedded content. If `None`, then the
    #: default guessing is used. If `True` then the we always assume the feeds has
    #: embedded content and if `False` we always assume the feed does not have
    #: embedded content.
    use_embedded_content   = None

    #: Set to True and implement :meth:`get_obfuscated_article` to handle
    #: websites that try to make it difficult to scrape content.
    articles_are_obfuscated = False

    #: Reverse the order of articles in each feed
    reverse_article_order = False

    #: Automatically extract all the text from downloaded article pages. Uses
    #: the algorithms from the readability project. Setting this to True, means
    #: that you do not have to worry about cleaning up the downloaded HTML
    #: manually (though manual cleanup will always be superior).
    auto_cleanup = False

    #: Specify elements that the auto cleanup algorithm should never remove.
    #: The syntax is a XPath expression. For example::
    #:
    #:   auto_cleanup_keep = '//div[@id="article-image"]' will keep all divs with
    #:                                                  id="article-image"
    #:   auto_cleanup_keep = '//*[@class="important"]' will keep all elements
    #:                                               with class="important"
    #:   auto_cleanup_keep = '//div[@id="article-image"]|//span[@class="important"]'
    #:                     will keep all divs with id="article-image" and spans
    #:                     with class="important"
    #:
    auto_cleanup_keep = ['image-block', 'image-block-caption', 'image-block-ins']

    #: Specify any extra :term:`CSS` that should be added to downloaded :term:`HTML` files.
    #: It will be inserted into `<style>` tags, just before the closing
    #: `</head>` tag thereby overriding all :term:`CSS` except that which is
    #: declared using the style attribute on individual :term:`HTML` tags.
    #: Note that if you want to programmatically generate the extra_css override
    #: the :meth:`get_extra_css()` method instead.
    #: For example::
    #:
    #:     extra_css = '.heading { font: serif x-large }'
    #:
    extra_css              = None

    #: If True empty feeds are removed from the output.
    #: This option has no effect if parse_index is overridden in
    #: the sub class. It is meant only for recipes that return a list
    #: of feeds using `feeds` or :meth:`get_feeds`. It is also used if you use
    #: the ignore_duplicate_articles option.
    remove_empty_feeds = True

    #: List of regular expressions that determines which links to follow.
    #: If empty, it is ignored. Used only if is_link_wanted is
    #: not implemented. For example::
    #:
    #:     match_regexps = [r'page=[0-9]+']
    #:
    #: will match all URLs that have `page=some number` in them.
    #:
    #: Only one of :attr:`BasicNewsRecipe.match_regexps` or
    #: :attr:`BasicNewsRecipe.filter_regexps` should be defined.
    match_regexps         = []

    #: List of regular expressions that determines which links to ignore.
    #: If empty it is ignored. Used only if is_link_wanted is not
    #: implemented. For example::
    #:
    #:     filter_regexps = [r'ads\.doubleclick\.net']
    #:
    #: will remove all URLs that have `ads.doubleclick.net` in them.
    #:
    #: Only one of :attr:`BasicNewsRecipe.match_regexps` or
    #: :attr:`BasicNewsRecipe.filter_regexps` should be defined.
    filter_regexps        = []

    #: Recipe specific options to control the conversion of the downloaded
    #: content into an e-book. These will override any user or plugin specified
    #: values, so only use if absolutely necessary. For example::
    #:
    #:   conversion_options = {
    #:     'base_font_size'   : 16,
    #:     'linearize_tables' : True,
    #:   }
    #:
    conversion_options = {}

    #: List of tags to be removed. Specified tags are removed from downloaded HTML.
    #: A tag is specified as a dictionary of the form::
    #:
    #:    {
    #:     name      : 'tag name',   #e.g. 'div'
    #:     attrs     : a dictionary, #e.g. {'class': 'advertisment'}
    #:    }
    #:
    #: All keys are optional. For a full explanation of the search criteria, see
    #: `Beautiful Soup <https://www.crummy.com/software/BeautifulSoup/bs4/doc/#searching-the-tree>`__
    #: A common example::
    #:
    #:   remove_tags = [dict(name='div', class_='advert')]
    #:
    #: This will remove all `<div class="advert">` tags and all
    #: their children from the downloaded :term:`HTML`.
    remove_tags           = []

    #: Remove all tags that occur after the specified tag.
    #: For the format for specifying a tag see :attr:`BasicNewsRecipe.remove_tags`.
    #: For example::
    #:
    #:     remove_tags_after = [dict(id='content')]
    #:
    #: will remove all
    #: tags after the first element with `id="content"`.
    remove_tags_after     = None

    #: Remove all tags that occur before the specified tag.
    #: For the format for specifying a tag see :attr:`BasicNewsRecipe.remove_tags`.
    #: For example::
    #:
    #:     remove_tags_before = dict(id='content')
    #:
    #: will remove all
    #: tags before the first element with `id="content"`.
    remove_tags_before    = None

    #: List of attributes to remove from all tags.
    #: For example::
    #:
    #:   remove_attributes = ['style', 'font']
    remove_attributes = []

    #: Keep only the specified tags and their children.
    #: For the format for specifying a tag see :attr:`BasicNewsRecipe.remove_tags`.
    #: If this list is not empty, then the `<body>` tag will be emptied and re-filled with
    #: the tags that match the entries in this list. For example::
    #:
    #:     keep_only_tags = [dict(id=['content', 'heading'])]
    #:
    #: will keep only tags that have an `id` attribute of `"content"` or `"heading"`.
    keep_only_tags        = []

    #: List of :term:`regexp` substitution rules to run on the downloaded :term:`HTML`.
    #: Each element of the
    #: list should be a two element tuple. The first element of the tuple should
    #: be a compiled regular expression and the second a callable that takes
    #: a single match object and returns a string to replace the match. For example::
    #:
    #:     preprocess_regexps = [
    #:        (re.compile(r'<!--Article ends here-->.*</body>', re.DOTALL|re.IGNORECASE),
    #:         lambda match: '</body>'),
    #:     ]
    #:
    #: will remove everything from `<!--Article ends here-->` to `</body>`.
    preprocess_regexps    = []

    #: The CSS that is used to style the templates, i.e., the navigation bars and
    #: the Tables of Contents. Rather than overriding this variable, you should
    #: use `extra_css` in your recipe to customize look and feel.
    template_css = '''.article_date {color: gray; font-family: monospace;}
        .article_description {text-indent: 0pt;}
        a.article {font-weight: bold; text-align:left;}
        a.feed {font-weight: bold;}
        .calibre_navbar {font-family:monospace;}'''

    #: By default, calibre will use a default image for the masthead (Kindle only).
    #: Override this in your recipe to provide a URL to use as a masthead.
    masthead_url = None

    # = None, set default cover
    # = False, no cover
    # = url, download url
    cover_url = None

    #: By default, the cover image returned by get_cover_url() will be used as
    #: the cover for the periodical.  Overriding this in your recipe instructs
    #: calibre to render the downloaded cover into a frame whose width and height
    #: are expressed as a percentage of the downloaded cover.
    #: cover_margins = (10, 15, '#ffffff') pads the cover with a white margin
    #: 10px on the left and right, 15px on the top and bottom.
    #: Color names are defined `here <https://www.imagemagick.org/script/color.php>`_.
    #: Note that for some reason, white does not always work in Windows. Use
    #: #ffffff instead
    cover_margins = (0, 0, '#ffffff')

    #: Set to a non empty string to disable this recipe.
    #: The string will be used as the disabled message
    recipe_disabled = None

    #: Ignore duplicates of articles that are present in more than one section.
    #: A duplicate article is an article that has the same title and/or URL.
    #: To ignore articles with the same title, set this to::
    #:
    #:   ignore_duplicate_articles = {'title'}
    #:
    #: To use URLs instead, set it to::
    #:
    #:   ignore_duplicate_articles = {'url'}
    #:
    #: To match on title or URL, set it to::
    #:
    #:   ignore_duplicate_articles = {'title', 'url'}
    ignore_duplicate_articles = None

    # The following parameters control how the recipe attempts to minimize
    # JPEG image sizes

    #: Set this to False to ignore all scaling and compression parameters and
    #: pass images through unmodified. If True and the other compression
    #: parameters are left at their default values, JPEG images will be scaled to fit
    #: in the screen dimensions set by the output profile and compressed to size at
    #: most (w * h)/16 where w x h are the scaled image dimensions.
    compress_news_images = True

    #: The factor used when auto compressing JPEG images. If set to None,
    #: auto compression is disabled. Otherwise, the images will be reduced in size to
    #: (w * h)/compress_news_images_auto_size bytes if possible by reducing
    #: the quality level, where w x h are the image dimensions in pixels.
    #: The minimum JPEG quality will be 5/100 so it is possible this constraint
    #: will not be met.  This parameter can be overridden by the parameter
    #: compress_news_images_max_size which provides a fixed maximum size for images.
    #: Note that if you enable scale_news_images_to_device then the image will
    #: first be scaled and then its quality lowered until its size is less than
    #: (w * h)/factor where w and h are now the *scaled* image dimensions. In
    #: other words, this compression happens after scaling.
    compress_news_images_auto_size = None #16

    #: Set JPEG quality so images do not exceed the size given (in KBytes).
    #: If set, this parameter overrides auto compression via compress_news_images_auto_size.
    #: The minimum JPEG quality will be 5/100 so it is possible this constraint
    #: will not be met.
    compress_news_images_max_size = None

    #: Rescale images to fit in the device screen dimensions set by the output profile.
    #: Ignored if no output profile is set.
    scale_news_images_to_device = True

    #: Maximum dimensions (w,h) to scale images to. If scale_news_images_to_device is True
    #: this is set to the device screen dimensions set by the output profile unless
    #: there is no profile set, in which case it is left at whatever value it has been
    #: assigned (default None).
    scale_news_images = None

    #: If set to True then links in downloaded articles that point to other downloaded articles are
    #: changed to point to the downloaded copy of the article rather than its original web URL. If you
    #: set this to True, you might also need to implement :meth:`canonicalize_internal_url` to work
    #: with the URL scheme of your particular website.
    resolve_internal_links = False

    #: Set to False if you do not want to use gzipped transfers. Note that some old servers flake out with gzip
    handle_gzip = True

    #: If this value is None, the value of the input option will be used.
    keep_images = None

    # set by worker.py
    translator = {}
    tts = {}
    delivery_reason = 'cron'

    # See the built-in recipes for examples of these settings.

    def short_title(self):
        return force_unicode(self.title, preferred_encoding)

    def is_link_wanted(self, url, tag):
        '''
        Return True if the link should be followed or False otherwise. By
        default, raises NotImplementedError which causes the downloader to
        ignore it.

        :param url: The URL to be followed
        :param tag: The tag from which the URL was derived
        '''
        raise NotImplementedError()

    def get_extra_css(self):
        '''
        By default returns `self.extra_css`. Override if you want to programmatically generate the
        extra_css.
        '''
        return self.extra_css

    def get_cover_url(self):
        '''
        Return a :term:`URL` to the cover image for this issue or `None`.
        By default it returns the value of the member `self.cover_url` which
        is normally `None`. If you want your recipe to download a cover for the e-book
        override this method in your subclass, or set the member variable `self.cover_url`
        before this method is called.
        '''
        return getattr(self, 'cover_url', None)

    def get_masthead_url(self):
        '''
        Return a :term:`URL` to the masthead image for this issue or `None`.
        By default it returns the value of the member `self.masthead_url` which
        is normally `None`. If you want your recipe to download a masthead for the e-book
        override this method in your subclass, or set the member variable `self.masthead_url`
        before this method is called.
        Masthead images are used in Kindle MOBI files.
        '''
        return getattr(self, 'masthead_url', None)

    def get_feeds(self):
        '''
        Return a list of :term:`RSS` feeds to fetch for this profile. Each element of the list
        must be a 2-element tuple of the form (title, url). If title is None or an
        empty string, the title from the feed is used. This method is useful if your recipe
        needs to do some processing to figure out the list of feeds to download. If
        so, override in your subclass.
        '''
        #if not self.feeds:
        #    raise NotImplementedError()
        if self.test and self.feeds:
            return self.feeds[:self.test[0]]
        return self.feeds

    def get_url_specific_delay(self, url):
        '''
        Return the delay in seconds before downloading this URL. If you want to programmatically
        determine the delay for the specified URL, override this method in your subclass, returning
        self.delay by default for URLs you do not want to affect.

        :return: A floating point number, the delay in seconds.
        '''
        return self.delay

    @classmethod
    def print_version(cls, url):
        '''
        Take a `url` pointing to the webpage with article content and return the
        :term:`URL` pointing to the print version of the article. By default does
        nothing. For example::

            def print_version(self, url):
                return url + '?&pagewanted=print'

        '''
        raise NotImplementedError()

    @classmethod
    def image_url_processor(cls, baseurl, url):
        '''
        Perform some processing on image urls (perhaps removing size restrictions for
        dynamically generated images, etc.) and return the precessed URL. Return None
        or an empty string to skip fetching the image.
        '''
        return url

    def preprocess_image(self, img_data, image_url):
        '''
        Perform some processing on downloaded image data. This is called on the raw
        data before any resizing is done. Must return the processed raw data. Return
        None to skip the image.
        '''
        return img_data

    def get_browser(self, *args, **kwargs):
        '''
        Return a browser instance used to fetch documents from the web. By default
        it returns a `mechanize <https://mechanize.readthedocs.io/en/latest/>`_
        browser instance that supports cookies, ignores robots.txt, handles
        refreshes and has a mozilla firefox user agent.

        If your recipe requires that you login first, override this method
        in your subclass. For example, the following code is used in the New York
        Times recipe to login for full access::

            def get_browser(self):
                br = BasicNewsRecipe.get_browser(self)
                if self.username is not None and self.password is not None:
                    br.open('https://www.nytimes.com/auth/login')
                    br.select_form(name='login')
                    br['USERID']   = self.username
                    br['PASSWORD'] = self.password
                    br.submit_selected()
                return br

        '''
        #if 'user_agent' not in kwargs:
        #    # More and more news sites are serving JPEG XR images to IE
        #    ua = getattr(self, 'last_used_user_agent', None) or self.calibre_most_common_ua or random_user_agent(allow_ie=False)
        #    kwargs['user_agent'] = self.last_used_user_agent = ua
        #self.log('Using user agent:', kwargs['user_agent'])
        kwargs.setdefault('file_stub', self.fs)
        return UrlOpener(**kwargs)

    def clone_browser(self, br):
        '''
        Clone the browser br. Cloned browsers are used for multi-threaded
        downloads, since mechanize is not thread safe. The default cloning
        routines should capture most browser customization, but if you do
        something exotic in your recipe, you should override this method in
        your recipe and clone manually.

        Cloned browser instances use the same, thread-safe CookieJar by
        default, unless you have customized cookie handling.
        '''
        #if callable(getattr(br, 'clone_browser', None)):
        #    return br.clone_browser()

        # Uh-oh recipe using something exotic, call get_browser
        #return self.get_browser()
        return br #requests是线程安全的

    @property
    def cloned_browser(self):
        #if hasattr(self.get_browser, 'is_base_class_implementation'):
            # We are using the default get_browser, which means no need to
            # clone
        #    br = BasicNewsRecipe.get_browser(self)
        #else:
        #    br = self.clone_browser(self.browser)
        return self.browser

    def get_article_url(self, article):
        '''
        Override in a subclass to customize extraction of the :term:`URL` that points
        to the content for each article. Return the
        article URL. It is called with `article`, an object representing a parsed article
        from a feed. See `feedparser <https://pythonhosted.org/feedparser/>`_.
        By default it looks for the original link (for feeds syndicated via a
        service like FeedBurner or Pheedo) and if found,
        returns that or else returns
        `article.link <https://pythonhosted.org/feedparser/reference-entry-link.html>`_.
        '''
        for key in article.keys():
            if key.endswith('_origlink'):
                url = article[key]
                if url and (url.startswith('http://') or url.startswith('https://')):
                    return url
        ans = article.get('link', None)
        if not ans and getattr(article, 'links', None):
            for item in article.links:
                if item.get('rel', 'alternate') == 'alternate':
                    ans = item['href']
                    break
        return ans

    def skip_ad_pages(self, soup):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, before
        any of the cleanup attributes like remove_tags, keep_only_tags are
        applied. Note that preprocess_regexps will have already been applied.
        It is meant to allow the recipe to skip ad pages. If the soup represents
        an ad page, return the HTML of the real page. Otherwise return
        None.

        `soup`: A `BeautifulSoup <https://www.crummy.com/software/BeautifulSoup/bs4/doc/>`__
        instance containing the downloaded :term:`HTML`.
        '''
        return None

    def abort_article(self, msg=None):
        ''' Call this method inside any of the preprocess methods to abort the
        download for the current article. Useful to skip articles that contain
        inappropriate content, such as pure video articles. '''
        raise AbortArticle(msg or _('Article download aborted'))

    def preprocess_raw_html(self, raw_html, url):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, before
        it is parsed into an object tree. raw_html is a unicode string
        representing the raw HTML downloaded from the web. url is the URL from
        which the HTML was downloaded.

        Note that this method acts *before* preprocess_regexps.

        This method must return the processed raw_html as a unicode object.
        '''
        return raw_html

    def preprocess_raw_html_(self, raw_html, url):
        raw_html = self.preprocess_raw_html(raw_html, url)
        if self.auto_cleanup:
            try:
                raw_html = self.extract_readable_article(raw_html, url)
            except:
                self.log.exception(loc_exc_pos(f'Auto cleanup of URL {url} failed'))

        return raw_html

    def preprocess_html(self, soup):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, before
        it is parsed for links and images. It is called after the cleanup as
        specified by remove_tags etc.
        It can be used to do arbitrarily powerful pre-processing on the :term:`HTML`.
        It should return `soup` after processing it.

        `soup`: A `BeautifulSoup <https://www.crummy.com/software/BeautifulSoup/bs4/doc/>`__
        instance containing the downloaded :term:`HTML`.
        '''
        return soup

    def postprocess_html(self, soup, first_fetch):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, after
        it is parsed for links and images.
        It can be used to do arbitrarily powerful post-processing on the :term:`HTML`.
        It should return `soup` after processing it.

        :param soup: A `BeautifulSoup <https://www.crummy.com/software/BeautifulSoup/bs4/doc/>`__  instance containing the downloaded :term:`HTML`.
        :param first_fetch: True if this is the first page of an article.

        '''
        return soup

    def cleanup(self):
        '''
        Called after all articles have been download. Use it to do any cleanup like
        logging out of subscription sites, etc.
        '''
        pass

    def canonicalize_internal_url(self, url, is_link=True):
        '''
        Return a set of canonical representations of ``url``.  The default
        implementation uses just the server hostname and path of the URL,
        ignoring any query parameters, fragments, etc. The canonical
        representations must be unique across all URLs for this news source. If
        they are not, then internal links may be resolved incorrectly.

        :param is_link: Is True if the URL is coming from an internal link in
                        an HTML file. False if the URL is the URL used to
                        download an article.
        '''
        try:
            parts = urlparse(url)
        except Exception:
            self.log.error('Failed to parse url: %r, ignoring' % url)
            return frozenset()
        nl = parts.netloc
        path = parts.path or ''
        if isinstance(nl, bytes):
            nl = nl.decode('utf-8', 'replace')
        if isinstance(path, bytes):
            path = path.decode('utf-8', 'replace')
        return frozenset({(nl, path.rstrip('/'))})

    def index_to_soup(self, url_or_raw, raw=False, as_tree=False, save_raw=None):
        '''
        Convenience method that takes an URL to the index page and returns
        a `BeautifulSoup <https://www.crummy.com/software/BeautifulSoup/bs4/doc>`__
        of it.

        `url_or_raw`: Either a URL or the downloaded index page as a string
        '''
        if re.match((br'\w+://' if isinstance(url_or_raw, bytes) else r'\w+://'), url_or_raw):
            # We may be called in a thread (in the skip_ad_pages method), so
            # clone the browser to be safe. We cannot use self.cloned_browser
            # as it may or may not actually clone the browser, depending on if
            # the recipe implements get_browser() or not
            _raw = None
            resp = self.browser.open(url_or_raw, timeout=self.timeout)
            if resp.status_code == 200:
                _raw = resp.content
            if not _raw:
                raise RuntimeError('Could not fetch index from %s'%url_or_raw)
        else:
            _raw = url_or_raw
        if raw:
            return _raw
        if not isinstance(_raw, str) and self.encoding:
            if callable(self.encoding):
                _raw = self.encoding(_raw)
            else:
                _raw = _raw.decode(self.encoding, 'replace')
        from calibre.ebooks.chardet import strip_encoding_declarations, xml_to_unicode
        from calibre.utils.cleantext import clean_xml_chars
        if isinstance(_raw, str):
            _raw = strip_encoding_declarations(_raw)
        else:
            _raw = xml_to_unicode(_raw, strip_encoding_pats=True, resolve_entities=True, assume_utf8=True)[0]
        _raw = clean_xml_chars(_raw)
        if save_raw:
            with open(save_raw, 'wb') as f:
                f.write(_raw.encode('utf-8'))
        if as_tree:
            from html5_parser import parse
            return parse(_raw)
        return BeautifulSoup(_raw, 'lxml')

    #使用自动算法提取正文
    def extract_readable_article(self, html: str, url: str):
        summary = title = ''
        try:
            doc = readability.Document(html, positive_keywords=self.auto_cleanup_keep, url=url)
            summary = doc.summary(html_partial=False)
            short_title = doc.short_title()
            title = short_title if short_title else doc.title()
        except:
            pass
        
        #内嵌函数，判断提取文本是否有足够的内容
        def summaryOk(summary):
            match = re.search(r'<body.*?>([\s\S]*?)<\/body>', summary, re.I|re.M)
            return match and (len(re.sub(r'<[\s\S]*?>', '', match.group(1), flags=re.I|re.M|re.S)) > 200)

        if not summaryOk(summary):
            import justext_extract #启用备用算法
            summary = justext_extract.justext_extract(html, self.language, url, debug=False)

            #判断是否再次失败
            if summaryOk(summary):
                self.log.debug(f'Extracted by alternative algorithm: {url}')
            else:
                raise Exception('Extract readable article algorithm failed, fallback to raw html.')

        #获取原本的title
        if not title:
            match = re.search(r'<title[^>]*>(.*?)</title>', html, re.I|re.M|re.S)
            title = match.group(1).strip() if match else 'Untitled'

        return self.update_or_add_title(summary, title)

    #添加或修改html的title
    def update_or_add_title(self, html: str, title: str):
        soup = BeautifulSoup(html, 'lxml')
        head = soup.find('head')
        if not head:
            head = soup.new_tag('head')
            soup.html.insert(0, head) #type:ignore

        title_tag = head.find('title')
        if title_tag:
            title_tag.string = title #type:ignore
        else:
            title_tag = soup.new_tag('title')
            title_tag.string = title
            head.append(title_tag)

        return str(soup)

    def sort_index_by(self, index, weights):
        '''
        Convenience method to sort the titles in `index` according to `weights`.
        `index` is sorted in place. Returns `index`.

        `index`: A list of titles.

        `weights`: A dictionary that maps weights to titles. If any titles
        in index are not in weights, they are assumed to have a weight of 0.
        '''
        weights = defaultdict(int, weights)
        index.sort(key=lambda x: weights[x])
        return index

    def parse_index(self):
        '''
        This method should be implemented in recipes that parse a website
        instead of feeds to generate a list of articles. Typical uses are for
        news sources that have a "Print Edition" webpage that lists all the
        articles in the current print edition. If this function is implemented,
        it will be used in preference to :meth:`BasicNewsRecipe.parse_feeds`.

        It must return a list. Each element of the list must be a 2-element tuple
        of the form ``('feed title', list of articles)``.

        Each list of articles must contain dictionaries of the form::

            {
            'title'       : article title,
            'url'         : URL of print version,
            'date'        : The publication date of the article as a string,
            'description' : A summary of the article
            'content'     : The full article (can be an empty string). Obsolete
                            do not use, instead save the content to a temporary
                            file and pass a file:///path/to/temp/file.html as
                            the URL.
            }

        For an example, see the recipe for downloading `The Atlantic`.
        In addition, you can add 'author' for the author of the article.

        If you want to abort processing for some reason and have
        calibre show the user a simple message instead of an error, call
        :meth:`abort_recipe_processing`.
        '''
        raise NotImplementedError()

    def abort_recipe_processing(self, msg):
        '''
        Causes the recipe download system to abort the download of this recipe,
        displaying a simple feedback message to the user.
        '''
        from calibre.ebooks.conversion import ConversionUserFeedBack
        raise ConversionUserFeedBack(_('Failed to download %s')%self.title,
                msg)

    def get_obfuscated_article(self, url):
        '''
        If you set `articles_are_obfuscated` this method is called with
        every article URL. It should return the path to a file on the filesystem
        that contains the article HTML. That file is processed by the recursive
        HTML fetching engine, so it can contain links to pages/images on the web.
        Alternately, you can return a dictionary of the form:
        {'data': <HTML data>, 'url': <the resolved URL of the article>}. This avoids
        needing to create temporary files. The `url` key in the dictionary is useful if
        the effective URL of the article is different from the URL passed into this method,
        for example, because of redirects. It can be omitted if the URL is unchanged.

        This method is typically useful for sites that try to make it difficult to
        access article content automatically.
        '''
        raise NotImplementedError()

    def add_toc_thumbnail(self, article, src):
        '''
        Call this from populate_article_metadata with the src attribute of an
        <img> tag from the article that is appropriate for use as the thumbnail
        representing the article in the Table of Contents. Whether the
        thumbnail is actually used is device dependent (currently only used by
        the Kindles). Note that the referenced image must be one that was
        successfully downloaded, otherwise it will be ignored.
        '''
        if not src or not hasattr(article, 'toc_thumbnail'):
            return

        src = src.replace('\\', '/')
        if re.search(r'feed_\d+/article_\d+/images/img', src, flags=re.I) is None:
            self.log.warn('Ignoring invalid TOC thumbnail image: %r'%src)
            return
        article.toc_thumbnail = re.sub(r'^.*?feed', 'feed',
                src, flags=re.IGNORECASE)

    def populate_article_metadata(self, article, soup, first):
        '''
        Called when each HTML page belonging to article is downloaded.
        Intended to be used to get article metadata like author/summary/etc.
        from the parsed HTML (soup).

        :param article: A object of class :class:`calibre.web.feeds.Article`.
            If you change the summary, remember to also change the text_summary
        :param soup: Parsed HTML belonging to this article
        :param first: True iff the parsed HTML is the first page of the article.
        '''
        pass

    def postprocess_book(self, oeb, opts, log):
        '''
        Run any needed post processing on the parsed downloaded e-book.

        :param oeb: An OEBBook object
        :param opts: Conversion options
        '''
        pass

    def __init__(self, options, log, output_dir, fs, feed_index_start=0):
        '''
        Initialize the recipe.
        :param options: Parsed commandline options
        :param log:  Logging object
        :param output_dir: output_dir name
        :param fs: FsDictStub object
        :parm feed_index_start: For multiple BasicNewsRecipe into one book
        '''
        if not os.path.isabs(str(output_dir)):
            raise Exception('output_dir have to be a abs path')
        self.log = log #ThreadSafeWrapper(log)
        if not isinstance(self.title, str):
            self.title = str(self.title, 'utf-8', 'replace')

        self.options = options
        self.user = self.options.user
        self.debug = options.verbose > 1
        self.output_dir = output_dir
        self.fs = fs
        self.feed_index_start = feed_index_start
        self.verbose = options.verbose
        self.test = options.test
        if self.test and not isinstance(self.test, tuple):
            self.test = (2, 2)
        self.lrf = options.lrf
        self.output_profile = options.output_profile
        self.touchscreen = getattr(self.output_profile, 'touchscreen', False)
        if self.touchscreen:
            self.template_css += self.output_profile.touchscreen_news_css
        if self.keep_images is None:
            self.keep_images = options.keep_images
            
        self.simultaneous_downloads = min(int(os.getenv('DOWNLOAD_THREAD_NUM', '1')), self.simultaneous_downloads)

        if self.test:
            self.max_articles_per_feed = self.test[1]
            self.simultaneous_downloads = min(4, self.simultaneous_downloads)

        if self.debug:
            self.verbose = True
        
        if self.needs_subscription and (self.username is None or self.password is None or 
            (not self.username and not self.password)):
            if self.needs_subscription != 'optional':
                raise ValueError(_('The "%s" recipe needs a username and password.')%self.title)

        self.browser = self.get_browser()
        self.image_map = {}
        self.image_counter = 1
        self.css_map = {}

        if options.output_profile.short_name in ('default', 'tablet'):
            self.scale_news_images_to_device = False
        elif self.scale_news_images_to_device:
            self.scale_news_images = options.output_profile.screen_size

        self.web2disk_options = wOpts = Web2diskOptions()
        for attr in ('keep_only_tags', 'remove_tags', 'preprocess_regexps', 'skip_ad_pages', 'preprocess_html', 
            'remove_tags_after', 'remove_tags_before', 'is_link_wanted', 'compress_news_images', 'keep_images',
            'compress_news_images_max_size', 'compress_news_images_auto_size', 'scale_news_images', 'filter_regexps',
            'match_regexps', 'no_stylesheets', 'verbose', 'delay', 'timeout', 'recursions', 'encoding'):
            setattr(wOpts, attr, getattr(self, attr))
            
        wOpts.keep_svg = getattr(options, 'keep_svg')
        wOpts.postprocess_html = self._postprocess_html
        wOpts.preprocess_image = self.preprocess_image
        wOpts.preprocess_raw_html = self.preprocess_raw_html_
        wOpts.get_delay = self.get_url_specific_delay
        wOpts.max_files = 0x7fffffff

        if self.delay > 0:
            self.simultaneous_downloads = 1

        #if self.touchscreen:
        #    self.navbar = templates.TouchscreenNavBarTemplate(feed_index_start=self.feed_index_start)
        #else:
        #    self.navbar = templates.NavBarTemplate(feed_index_start=self.feed_index_start)
        self.failed_downloads = []
        self.partial_failures = []
        self.aborted_articles = []
        self.article_url_map = defaultdict(set)

    def _postprocess_html(self, soup, first_fetch, job_info):
        if self.no_stylesheets:
            for link in list(soup.find_all('link')):
                if (link.get('type') or 'text/css').lower() == 'text/css' and 'stylesheet' in (link.get('rel') or ('stylesheet',)):
                    link.extract()
            for style in list(soup.find_all('style')):
                style.extract()

        head = soup.find('head')
        if not head:
            head = soup.new_tag('head')
            soup.html.insert(0, head)

        title_tag = head.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True) or 'Untitled'
        else: #创建一个Title
            title = (job_info.article.title if job_info else '') or 'Untitled'
            title_tag = soup.new_tag('title')
            title_tag.string = title
            head.append(title_tag)

        extra_css = self.get_extra_css()
        css = self.template_css + (('\n\n' + extra_css) if extra_css else '')
        style = soup.new_tag('style', type='text/css', title='override_css')
        style.append(css)
        head.append(style)
        if 0 and first_fetch and job_info:
            body = soup.find('body')
            if body is not None:
                templ = self.navbar.generate(False, job_info.f_idx, job_info.a_idx, job_info.feed_len,
                                             not self.has_single_feed,
                                             job_info.url, __appname__,
                                             center=self.center_navbar,
                                             extra_css=self.get_extra_css() or '')
                elem = BeautifulSoup(templ.render(doctype='xhtml').decode('utf-8'), 'lxml').find('div')
                body.insert(0, elem)
                # This is needed because otherwise inserting elements into
                # the soup breaks find()
                soup = BeautifulSoup(soup.decode_contents(), 'lxml')
        if self.remove_javascript:
            for script in list(soup.find_all('script')):
                script.extract()
            for o in soup.find_all(onload=True):
                del o['onload']

        #选择所有带有横杠属性名的属性，并删除它们，因为epub不支持这些属性
        for tag in soup.find_all(lambda t: any(a for a in t.attrs if ('-' in a) or (a in self.remove_attributes))):
            tag.attrs = {key: val for key, val in tag.attrs.items() 
                if ('-' not in key) and (key not in self.remove_attributes)}

        #for attr in self.remove_attributes:
        #    for x in soup.find_all(attrs={attr: True}):
        #        del x[attr]

        for bad_tag in list(soup.find_all(['base', 'iframe', 'canvas', 'embed', 'source',
            'command', 'datalist', 'video', 'audio', 'noscript', 'link', 'meta', 'button'])):
            bad_tag.extract()
        
        #如果需要，去掉正文中的超链接(使用斜体下划线标识)，以避免误触
        remove_hyperlinks = self.user.book_cfg('rm_links')
        if remove_hyperlinks in ('text', 'all'):
            for a_ in soup.find_all('a'):
                a_.name = 'i'
                a_.attrs.clear()

        #去掉图像上面的链接，以免误触后打开浏览器，同时如果使用了picture标签，删除picture
        rmImgLinks = remove_hyperlinks in ('image', 'all')
        for tag in soup.find_all('img'):
            parent = tag.parent
            grParent = parent.parent if parent else None
            if parent and grParent:
                if rmImgLinks and (parent.name == 'a'):
                    parent.replace_with(tag)
                elif parent.name == 'picture':
                    parent.replace_with(tag)
                elif grParent.parent and (grParent.name == 'picture'):
                    grParent.replace_with(tag)

        #kindle不支持内嵌title的svg
        keep_svg = getattr(self.options, 'keep_svg')
        for svg in soup.find_all('svg'):
            if keep_svg:
                tag = svg.find('title')
                if tag:
                    tag.extract()
            else:
                svg.extract()
        
        #除了toc里面有标题，内容开头也要有标题，方便阅读
        body_tag = soup.find("body")
        if body_tag:
            h_tag = body_tag.find(['h1','h2']) #type:ignore
            #也要判断此H1/H2是否在文章中间出现，如果是则不是文章标题
            if not h_tag or any(len(tag.get_text(strip=True)) > 100 for tag in h_tag.previous_siblings): #type:ignore
                h_tag = soup.new_tag('h2')
                h_tag.string = title
                body_tag.insert(0, h_tag)
            elif h_tag: #去掉标题前面的部分内容
                for tag in h_tag.previous_siblings: #type:ignore
                    if len(tag.get_text(strip=True)) < 20:
                        tag.extract()
                if not h_tag.get_text(strip=True):
                    h_tag.string = title

        #job_info.article.url才是真实的url，对于内嵌内容RSS，job_info.url为一个临时文件名
        self.append_share_links(soup, url=job_info.article.url)
        
        ans = self.postprocess_html(soup, first_fetch)

        # Nuke HTML5 tags
        for x in ans.find_all(['article', 'aside', 'header', 'footer', 'nav', 'main',
            'figcaption', 'figure', 'section', 'time']):
            x.name = 'div'

        #for x in ans.find_all('mark'):
        #    x.name = 'strong'

        #If tts need, tts propery is set by WorkerImpl
        tts_enable = self.tts.get('enable')
        if tts_enable:
            self.audiofy_html(soup, title, job_info)

        #If translation need, translator propery is set by WorkerImpl
        if self.translator.get('enable') and (tts_enable != 'audio_only'):
            self.translate_html(soup, title)

        if job_info:
            try:
                if job_info.article:
                    article = job_info.article
                else:
                    article = self.feed_objects[job_info.f_idx - self.feed_index_start].articles[job_info.a_idx]
            except:
                self.log.exception('Failed to get article object for postprocessing')
                pass
            else:
                self.populate_article_metadata(article, ans, first_fetch)
        return ans

    #在文章末尾添加分享链接
    def append_share_links(self, soup, url):
        if not soup:
            return
        
        shareLinks = self.user.share_links
        aTags = []
        for type_ in ['Evernote', 'Wiz', 'Pocket', 'Instapaper', 'wallabag']:
            if shareLinks.get(type_, {}).get('enable'):
                ashare = soup.new_tag('a', href=self.make_share_link(type_, self.user, url, soup))
                ashare.string = _('Save to {}').format(type_)
                aTags.append(ashare)

        for type_ in ['Weibo', 'Facebook', 'X', 'Tumblr']:
            if shareLinks.get(type_):
                ashare = soup.new_tag('a', href=self.make_share_link(type_, self.user, url, soup))
                ashare.string =  _('Share on {}').format(type_)
                aTags.append(ashare)

        if shareLinks.get('Browser'):
            ashare = soup.new_tag('a', href=url)
            ashare.string = _('Open in browser')
            aTags.append(ashare)

        #将上面创建的链接都添加到body
        bodyTag = soup.find("body")
        if aTags:
            div = soup.new_tag("div")
            hr = soup.new_tag("hr")
            div.append(hr)
            for idx, a in enumerate(aTags):
                div.append(a)
                if idx < len(aTags) - 1:
                    span = soup.new_tag("span")
                    span.string = ' | '
                    div.append(span)
            bodyTag.append(div)

        #如果有需要二维码功能，最后添加
        if shareLinks.get('Qrcode'):
            import qrcode
            qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image()
            buffer = io.BytesIO()
            img.save(buffer, 'PNG')
            qrBase64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            #div.append(soup.new_tag('br'))
            div = soup.new_tag("div") #单独一个div
            div.append(soup.new_tag('img', src=f"data:image/png;base64,{qrBase64}", alt="qrcode"))
            bodyTag.append(div)

    #生成保存内容或分享文章链接的KindleEar调用链接
    def make_share_link(self, shareType, user, url, soup):
        share_key = user.share_links.get('key', '')
        titleTag = soup.find('title')
        url = quote(url)
        title = quote(titleTag.string if titleTag else 'Untitled')
        appDomain = os.getenv('APP_DOMAIN')
        if shareType in ('Evernote', 'Wiz'):
            href = f"{appDomain}/share?act={shareType}&u={user.name}&t={title}&k={share_key}&url={url}"
        elif shareType == 'Pocket':
            href = f'{appDomain}/share?act=Pocket&u={user.name}&t={title}&k={share_key}&url={url}'
        elif shareType == 'Instapaper':
            href = f'{appDomain}/share?act=Instapaper&u={user.name}&t={title}&k={share_key}&url={url}'
        elif shareType == 'wallabag':
            href = f'{appDomain}/share?act=wallabag&u={user.name}&t={title}&k={share_key}&url={url}'
        elif shareType == 'Weibo':
            href = f'https://service.weibo.com/share/share.php?url={url}'
        elif shareType == 'Facebook':
            href = f'https://www.facebook.com/share.php?u={url}'
        elif shareType == 'X':
            href = f'https://twitter.com/intent/post?text={title}&url={url}'
        elif shareType == 'Tumblr':
            href = f'https://www.tumblr.com/share/link?url={url}'
        else:
            href = ''

        return href

    #外部调用此函数实际下载
    def download(self):
        '''
        Download and pre-process all articles from the feeds in this recipe.
        This method should be called only once on a particular Recipe instance.
        Calling it more than once will lead to undefined behavior.
        :return: Path to index.html
        '''
        try:
            res = self.build_index()
            if self.failed_downloads:
                self.log.debug('Failed to download the following articles:')
                for feed, article, debug in self.failed_downloads:
                    self.log.debug(f'    {article.title} from {feed.title}')
                    self.log.debug(article.url)
                    self.log.debug(debug)
            if self.partial_failures:
                self.log.debug('Failed to download parts of the following articles:')
                for feed, atitle, aurl, debug in self.partial_failures:
                    self.log.debug(f'    {atitle} from {feed}')
                    self.log.debug(aurl)
                    self.log.debug('\tFailed links:')
                    for l, tb in debug:
                        self.log.debug(l)
                        self.log.debug(tb)
            return res
        finally:
            self.cleanup()
            #如果设置为仅推送音频，则删掉feed实例
            if self.tts.get('enable') == 'audio_only':
                self.feed_objects = []

    @property
    def lang_for_html(self):
        try:
            lang = self.language.replace('_', '-').partition('-')[0].lower()
            if lang == 'und':
                lang = None
        except:
            lang = None
        return lang

    #从Feed实例列表生成最顶层的index.html内容
    #<img src=Masthead></img>
    #<ul>
    #  <li id="feed_0"><a href="feed_0/index.html">Feed1 Title</a></li>
    #  <li id="feed_1"><a href="feed_1/index.html">Feed2 Title</a></li>
    #  ...
    #</ul>
    def feeds2index(self, feeds):
        templ = (templates.TouchscreenIndexTemplate if self.touchscreen else
                templates.IndexTemplate)
        templ = templ(lang=self.lang_for_html, feed_index_start=self.feed_index_start)
        css = self.template_css + '\n\n' +(self.get_extra_css() or '')
        timefmt = self.timefmt
        return templ.generate(self.title, DEFAULT_MASTHEAD_IMAGE, timefmt, feeds, extra_css=css).render(doctype='xhtml')

    @classmethod
    def description_limiter(cls, src):
        if not src:
            return ''
        src = force_unicode(src, 'utf-8')
        pos = cls.summary_length
        fuzz = 50
        si = src.find(';', pos)
        if si > 0 and si-pos > fuzz:
            si = -1
        gi = src.find('>', pos)
        if gi > 0 and gi-pos > fuzz:
            gi = -1
        npos = max(si, gi)
        if npos < 0:
            npos = pos
        ans = src[:npos+1]
        if len(ans) < len(src):
            from calibre.utils.cleantext import clean_xml_chars

            # Truncating the string could cause a dangling UTF-16 half-surrogate, which will cause lxml to barf, clean it
            ans = clean_xml_chars(ans) + '\u2026'
        return ans

    #生成Feed对应的html内容，一个Feed就是根据一个Rss xml生成的html，里面会有多篇文章
    def feed2index(self, f, feeds):
        feed = feeds[f - self.feed_index_start]
        if feed.image_url is not None:  # Download feed image
            imgdir = os.path.join(self.output_dir, 'images')
            self.fs.makedirs(imgdir)
            
            if feed.image_url in self.image_map:
                feed.image_url = self.image_map[feed.image_url]
            else:
                bn = urlsplit(feed.image_url).path
                if bn:
                    bn = bn.rpartition('/')[-1] #basename
                    if bn:
                        img = os.path.join(imgdir, 'feed_image_%d%s'%(self.image_counter, os.path.splitext(bn)[-1]))
                        try:
                            resp = self.browser.open(feed.image_url, timeout=self.timeout)
                            if resp.status_code == 200:
                                self.fs.write(img, resp.content, 'wb')
                                self.image_counter += 1
                                feed.image_url = img
                                self.image_map[feed.image_url] = img
                        except:
                            pass
            if isinstance(feed.image_url, bytes):
                feed.image_url = feed.image_url.decode(sys.getfilesystemencoding(), 'strict')

        templ = (templates.TouchscreenFeedTemplate if self.touchscreen else
                    templates.FeedTemplate)
        templ = templ(lang=self.lang_for_html, feed_index_start=self.feed_index_start)
        css = self.template_css + '\n\n' +(self.get_extra_css() or '')

        return templ.generate(f, feeds, self.description_limiter, extra_css=css).render(doctype='xhtml')

    #下载一个url指定的网页和其内部的所有链接
    #返回：(file, downloads[], failures[]): 
    #       file: url网页内容保存的文件名
    #       downloads[]: 网页内的链接所对应的图像文件保存的文件名
    #       failures[]: 下载失败的url列表
    def _fetch_article(self, job_info, preloaded=None):
        url = job_info.url
        br = self.browser
        self.web2disk_options.browser = br
        self.web2disk_options.dir = job_info.art_dir
        if self.tts.get('enable') == 'audio_only':
            self.web2disk_options.keep_images = False
        
        fetcher = RecursiveFetcher(self.web2disk_options, self.fs, self.log, job_info, self.image_map, self.css_map)
        fetcher.browser = br
        fetcher.base_dir = job_info.art_dir
        fetcher.current_dir = job_info.art_dir
        fetcher.show_progress = False
        fetcher.image_url_processor = self.image_url_processor
        if preloaded is not None:
            fetcher.preloaded_urls[url] = preloaded
        
        res = fetcher.start_fetch(url)  #res为对应url的一个html文件名

        path = fetcher.downloaded_paths
        failures = fetcher.failed_links
        if not res or not self.fs.exists(res):
            msg = _('Could not fetch article.') + ' ' + url + ' '
            if self.debug:
                msg += _('The debug traceback is available earlier in this log')
            else:
                msg += _('Run with -vv to see the reason')
            raise Exception(msg)

        return res, path, failures

    #article: calibre.web.feeds.__init__.Article 实例
    def fetch_article(self, job_info):
        return self._fetch_article(job_info)

    #article: calibre.web.feeds.__init__.Article 实例
    def fetch_obfuscated_article(self, job_info):
        url = job_info.url
        x = self.get_obfuscated_article(url)
        if isinstance(x, dict):
            data = x['data']
            if isinstance(data, str):
                data = data.encode(self.encoding or 'utf-8')
            url = x.get('url', url)
        else:
            data = self.fs.read(x, 'rb')
            self.fs.delete(x)
        return self._fetch_article(job_info, preloaded=data)

    #下载全文RSS
    #这里为什么不将生成的html直接保存到目标位置是因为接下来要使用RecursiveFetcher下载里面的图像文件
    def fetch_embedded_article(self, job_info):
        templ = templates.EmbeddedContent()
        raw = templ.generate(job_info.article).render('html') #raw是utf-8编码的二进制内容
        with self.fs.make_tempfile(suffix='_feeds2disk.html', dir=self.output_dir) as pt:
            pt.write(raw)
            url = 'file://' + pt.name

        new_job_info = JobInfo(url, job_info.art_dir, job_info.f_idx, job_info.a_idx, job_info.feed_len, job_info.article)
        return self._fetch_article(new_job_info)

    def remove_duplicate_articles(self, feeds):
        seen_keys = defaultdict(set)
        remove = []
        for f in feeds:
            for article in f:
                for key in self.ignore_duplicate_articles:
                    val = getattr(article, key)
                    seen = seen_keys[key]
                    if val:
                        if val in seen:
                            remove.append((f, article))
                        else:
                            seen.add(val)

        for feed, article in remove:
            self.log.debug('Removing duplicate article: %s from section: %s'%(
                article.title, feed.title))
            feed.remove_article(article)

        if self.remove_empty_feeds:
            feeds = [f for f in feeds if len(f) > 0]
        return feeds

    #如果有多个Recipe一起生成一本电子书，每个的index.html名字不一样
    #index.html, index_10.html, ...
    def get_root_index_html_name(self):
        suffix = '.html' if self.feed_index_start == 0 else f'_{self.feed_index_start}.html'
        return f'index{suffix}'

    #实际下载feeds并创建index.html
    def build_index(self):
        feeds = None
        index = None
        try:
            index = self.parse_index()
        except NotImplementedError:
            pass
        except:
            self.log.warning(loc_exc_pos('parse_index() failed'))

        if index:
            feeds = feeds_from_index(index, oldest_article=self.oldest_article,
                                     max_articles_per_feed=self.max_articles_per_feed,
                                     log=self.log)
        
        if feeds is None:
            feeds = self.parse_feeds()

        if not feeds:
            raise ValueError('No articles found, aborting')

        if self.ignore_duplicate_articles is not None:
            feeds = self.remove_duplicate_articles(feeds)
            
        if self.feed_index_start == 0:
            self.download_cover()
            self.resolve_masthead()
        else:
            self.cover_path = None
            self.masthead_path = None
            
        if self.test:
            feeds = feeds[:self.test[0]]
        self.has_single_feed = (len(feeds) == 1)
        
        html = self.feeds2index(feeds)
        #如果是多个BasicNewsRecipe一起生成电子书的话，第一个为index.html，之后的index_num.html
        index = os.path.join(self.output_dir, self.get_root_index_html_name())
        self.fs.write(index, html, 'wb')

        self.jobs = []

        if self.reverse_article_order:
            for feed in feeds:
                if hasattr(feed, 'reverse'):
                    feed.reverse()

        self.feed_objects = feeds
        for f, feed in enumerate(feeds, self.feed_index_start):
            feed_dir = os.path.join(self.output_dir, f'feed_{f}')
            self.fs.makedirs(feed_dir)

            for a, article in enumerate(feed):
                if a >= self.max_articles_per_feed:
                    break

                art_dir = os.path.join(feed_dir, f'article_{a}')
                self.fs.makedirs(art_dir)

                try:
                    url = self.print_version(article.url)
                except NotImplementedError:
                    url = article.url
                except:
                    self.log.exception(loc_exc_pos(f'Failed to find print version for {article.url}'))
                    url = None
                if not url:
                    continue

                #设置多线程爬取网页的回调函数
                job_info = JobInfo(url, art_dir, f, a, len(feed), article)
                if self.use_embedded_content or (self.use_embedded_content is None and feed.has_embedded_content()):
                    func = self.fetch_embedded_article #全文RSS
                elif self.articles_are_obfuscated:
                    func = self.fetch_obfuscated_article #需要解密的文章
                else:
                    func = self.fetch_article #普通RSS

                #param:        callable, args,   kwds, requestID, callback,            exc_callback):
                req = WorkRequest(func, job_info, {}, (f, a), self.article_downloaded, self.error_in_article_download)
                req.feed = feed
                req.article = article
                req.feed_dir = feed_dir
                self.jobs.append(req)

        self.jobs_done = 0
        trans_enable = self.translator.get('enable') or self.tts.get('enable')
        #如果翻译使能，则不能使用多线程，否则容易触发流量告警导致IP被封锁
        if (self.simultaneous_downloads > 1) and not trans_enable:
            tp = ThreadPool(self.simultaneous_downloads)
            for req in self.jobs:
                tp.putRequest(req, block=True, timeout=0)

            while True:
                try:
                    tp.poll()
                    time.sleep(0.1)
                except NoResultsPending:
                    break
        else: #如果是单线程，为了更好的兼容性，在同一个线程抓取网页，上面的线程池即使是单线程，也是另一个线程
            for req in self.jobs:
                try:
                    req.callback(req, req.callable(req.args, **req.kwds))
                except:
                    import traceback
                    req.exception = True
                    req.exc_callback(req, traceback.format_exc())

        #统计Recipe的文章实际下载数量
        article_num = sum(1 for feed in feeds for article in feed if article.downloaded)
        if not article_num:
            raise ValueError('No articles downloaded, aborting')

        #翻译Feed的标题
        if self.translator.get('enable'):
            self.translate_titles(feeds)
        
        for f, feed in enumerate(feeds, self.feed_index_start):
            html = self.feed2index(f, feeds) #生成每个feed对应的html，都叫index.html
            feed_dir = os.path.join(self.output_dir, f'feed_{f}', 'index.html')
            self.fs.write(feed_dir, html, 'wb')
        
        #在recipe_input.py里面调用，可以一次性将多个Recipe的下载合并转换为一本电子书
        #self.create_opf(feeds)

        return index

    def _download_cover(self):
        self.cover_path = None
        try:
            cu = self.get_cover_url()
        except Exception as err:
            self.log.error(_('Could not download cover: %s')%as_unicode(err))
            self.log.debug(traceback.format_exc())
        else:
            if not cu:
                return
            cdata = None
            if hasattr(cu, 'read'): #一个文件类的对象
                cdata = cu.read()
                cu = getattr(cu, 'name', 'cover.jpg')
            elif os.access(cu, os.R_OK): #recipe里面设置了本地封面图像文件
                cdata = self.fs.read(cu, 'rb')
            else: #要求使用网络图像做为封面
                resp = self.browser.open(cu, timeout=self.timeout)
                if resp.status_code == 200:
                    cdata = resp.content
            if not cdata:
                return

            cdata = save_cover_data_to(cdata, resize_to=COVER_SIZE)
            self.cover_path = os.path.join(self.output_dir, 'cover.jpg')
            self.fs.write(self.cover_path, cdata, 'wb')
    
    #如果设置了cover_url，则从网络下载封面图片
    def download_cover(self):
        self.cover_path = None
        try:
            self._download_cover()
        except:
            self.log.exception('Failed to download cover')
            self.cover_path = None

    def _download_masthead(self, mu):
        #if hasattr(mu, 'rpartition'):
        #    ext = mu.rpartition('.')[-1]
        #    if '?' in ext:
        #        ext = ''
        #else:
        #    ext = mu.name.rpartition('.')[-1]
        #ext = ext.lower() if ext else 'jpg'
        #mpath = os.path.join(self.output_dir, 'masthead_source.' + ext)
        outfile = os.path.join(self.output_dir, DEFAULT_MASTHEAD_IMAGE)
        mdata = None
        if hasattr(mu, 'read'):
            mdata = mu.read()
        elif os.access(mu, os.R_OK):
            mdata = open(mu, 'rb').read()
        else:
            resp = self.browser.open(mu, timeout=self.timeout)
            if resp.status_code == 200:
                mdata = resp.content

        if mdata:
            self.prepare_masthead_image(mdata, outfile)
            self.masthead_path = outfile
        
    def download_masthead(self, url):
        try:
            self._download_masthead(url)
        except Exception as e:
            self.log.exception(f"Failed to download supplied masthead_url: {e}")

    def resolve_masthead(self):
        self.masthead_path = None
        try:
            murl = self.get_masthead_url()
        except:
            self.log.exception('Failed to get masthead url')
            murl = None

        if murl is not None:
            if isinstance(murl, (tuple, list)):
                murl = murl[0]
            # Try downloading the user-supplied masthead_url
            # Failure sets self.masthead_path to None
            self.download_masthead(murl)

        if self.masthead_path is None:
            #self.log.info("Synthesizing mastheadImage")
            self.masthead_path = os.path.join(self.output_dir, DEFAULT_MASTHEAD_IMAGE)
            try:
                masthead_raw_data = self.default_masthead_image()
            except:
                self.log.exception('Failed to generate default masthead image')
                self.masthead_path = None

            self.fs.write(self.masthead_path, masthead_raw_data, 'wb')

    def default_cover(self, cover_file):
        return

    def get_masthead_title(self):
        'Override in subclass to use something other than the recipe title'
        return self.title

    @classmethod
    def default_masthead_image(cls):
        with open(os.path.join(appDir, 'application', 'images', DEFAULT_MASTHEAD_IMAGE), 'rb') as f:
            return f.read()

        #from calibre.ebooks import generate_masthead
        #generate_masthead(self.get_masthead_title(), output_path=out_path,
        #        width=self.MI_WIDTH, height=self.MI_HEIGHT)

    def prepare_masthead_image(self, data, out_path):
        save_cover_data_to(data, out_path, resize_to=MASTHEAD_SIZE)
        #prepare_masthead_image(path_to_image, out_path, self.MI_WIDTH, self.MI_HEIGHT)
    
    def publication_date(self):
        '''
        Use this method to set the date when this issue was published.
        Defaults to the moment of download. Must return a :class:`datetime.datetime`
        object.
        '''
        #return nowf()
        return self.user.local_time()

    #现在这个函数已经不用，使用recipe_input.py里面的create_opf()
    #通过Feed对象列表构建一个opf文件
    #feeds: Feed对象列表
    #dir_: 将opf保存到哪个目录
    def create_opf(self, feeds, dir_=None):
        if dir_ is None:
            dir_ = self.output_dir
        title = self.short_title()
        pdate = self.publication_date()
        if self.output_profile.periodical_date_in_title:
            title += strftime(self.timefmt, pdate)
        mi = MetaInformation(title, ['KindleEar'])
        mi.publisher = 'KindleEar'
        mi.author_sort = 'KindleEar'
        if self.publication_type:
            mi.publication_type = 'periodical:'+self.publication_type+':'+self.short_title()
        mi.timestamp = nowf()
        article_titles, aseen = [], set()
        for (af, aa) in self.aborted_articles:
            aseen.add(aa.title)
        for (ff, fa, tb) in self.failed_downloads:
            aseen.add(fa.title)
        for f in feeds:
            for a in f:
                if a.title and a.title not in aseen:
                    aseen.add(a.title)
                    article_titles.append(force_unicode(a.title, 'utf-8'))

        desc = self.description
        if not isinstance(desc, str):
            desc = desc.decode('utf-8', 'replace')
        mi.comments = (_('Articles in this issue:'
            ) + '\n\n' + '\n\n'.join(article_titles)) + '\n\n' + desc

        language = canonicalize_lang(self.language)
        if language is not None:
            mi.language = language
        mi.pubdate = pdate
        
        opf = OPFCreator(dir_, mi, self.fs)
        # Add mastheadImage entry to <guide> section
        mp = getattr(self, 'masthead_path', None)
        if mp is not None: # and os.access(mp, os.R_OK):
            from calibre.ebooks.metadata.opf2 import Guide
            ref = Guide.Reference(os.path.basename(self.masthead_path), dir_)
            ref.type = 'masthead'
            ref.title = 'Masthead Image'
            opf.guide.append(ref)

        manifest = [os.path.join(dir_, 'feed_%d'% (i + self.feed_index_start)) for i in range(len(feeds))]
        manifest.append(os.path.join(dir_, 'index.html'))
        
        # Get cover
        #cpath = getattr(self, 'cover_path', None)
        #if cpath is None and self.feed_index_start == 0: #只要第一个News生成封面
        #    cover_data = get_default_cover_data()
        #    cpath = os.path.join(dir_, 'cover.jpg')
        #    self.cover_path = cpath
        #    self.fs.write(cpath, cover_data, 'wb')
        #opf.cover = cpath
        #manifest.append(cpath)

        # Get masthead
        mpath = getattr(self, 'masthead_path', None)
        if mpath is not None: # and os.access(mpath, os.R_OK):
            manifest.append(os.path.join(dir_, mpath))

        opf.create_manifest_from_files_in(manifest)

        #上面的语句执行时ncx还没有生成，要在函数末才生成，需要手动添加
        opf.manifest.add_item(os.path.join(dir_, 'index.ncx'), mime_type="application/x-dtbncx+xml")

        for mani in opf.manifest:
            if mani.path.endswith('.ncx'):
                mani.id = 'ncx'
            if mani.path.endswith(DEFAULT_MASTHEAD_IMAGE):
                mani.id = 'masthead-image'

        entries = ['index.html']
        toc = TOC(base_path=dir_)
        self.play_order_counter = 0
        self.play_order_map = {}

        aumap = self.article_url_map

        def feed_index(num, parent):
            f = feeds[num]
            for j, a in enumerate(f):
                if getattr(a, 'downloaded', False):
                    adir = 'feed_%d/article_%d/'%(num, j)
                    auth = a.author
                    if not auth:
                        auth = None
                    desc = a.text_summary
                    if not desc:
                        desc = None
                    else:
                        desc = self.description_limiter(desc)
                    tt = a.toc_thumbnail if a.toc_thumbnail else None
                    entries.append('%sindex.html'%adir)
                    po = self.play_order_map.get(entries[-1], None)
                    if po is None:
                        self.play_order_counter += 1
                        po = self.play_order_counter
                    arelpath = '%sindex.html'%adir
                    for curl in self.canonicalize_internal_url(a.orig_url, is_link=False):
                        aumap[curl].add(arelpath)
                    article_toc_entry = parent.add_item(arelpath, None,
                            a.title if a.title else _('Untitled article'),
                            play_order=po, author=auth,
                            description=desc, toc_thumbnail=tt)
                    for entry in a.internal_toc_entries:
                        anchor = entry.get('anchor')
                        if anchor:
                            self.play_order_counter += 1
                            po += 1
                            article_toc_entry.add_item(
                                arelpath, entry['anchor'], entry['title'] or _('Unknown section'),
                                play_order=po
                            )
                    #这段注释后的代码是添加navbar的
                    #last = os.path.join(adir, 'index.html')
                    #src = None
                    #last = os.path.join(self.output_dir, last)
                    #for sp in a.sub_pages:
                    #    prefix = os.path.commonprefix([opf_path, sp])
                    #    relp = sp[len(prefix):]
                    #    entries.append(relp.replace(os.sep, '/'))
                    #    last = sp
                    #if os.path.exists(last):
                    #    with open(last, 'rb') as fi:
                    #        src = fi.read().decode('utf-8')
                    #if src:
                        #soup = BeautifulSoup(src, 'lxml')
                        #body = soup.find('body')
                        #if body is not None:
                            #prefix = '/'.join('..'for i in range(2*len(re.findall(r'link\d+', last))))
                            #templ = self.navbar.generate(True, num, j, len(f),
                            #                not self.has_single_feed,
                            #                a.orig_url, __appname__, prefix=prefix,
                            #                center=self.center_navbar)
                            #elem = BeautifulSoup(templ.render(doctype='xhtml').decode('utf-8'), 'lxml').find('div')
                            #body.insert(len(body.contents), elem)
                        #    with open(last, 'wb') as fi:
                        #        fi.write(str(soup).encode('utf-8'))
        if len(feeds) == 0:
            raise Exception('All feeds are empty, aborting.')

        if len(feeds) > 1:
            for i, f in enumerate(feeds, self.feed_index_start):
                entries.append('feed_%d/index.html'%i)
                po = self.play_order_map.get(entries[-1], None)
                if po is None:
                    self.play_order_counter += 1
                    po = self.play_order_counter
                auth = getattr(f, 'author', None)
                if not auth:
                    auth = None
                desc = getattr(f, 'description', None)
                if not desc:
                    desc = None
                feed_index(i, toc.add_item('feed_%d/index.html'%i, None,
                    f.title, play_order=po, description=desc, author=auth))

        else:
            entries.append('feed_%d/index.html' % self.feed_index_start)
            feed_index(self.feed_index_start, toc)

        for i, p in enumerate(entries):
            entries[i] = os.path.join(dir_, p.replace('/', os.sep))
        opf.create_spine(entries)
        opf.set_toc(toc)

        opf_file = io.BytesIO()
        ncx_file = io.BytesIO()
        opf.render(opf_file, ncx_file)
        opf_path = os.path.join(dir_, 'index.opf')
        ncx_path = os.path.join(dir_, 'index.ncx')
        self.fs.write(opf_path, opf_file.getvalue(), 'wb')
        self.fs.write(ncx_path, ncx_file.getvalue(), 'wb')

    #文章下载完成后会回调此函数
    #request: 传给线程池的请求对象 calibre.utils.threadpool.WorkRequest
    #result: _fetch_article()执行结果，一个元祖 (file, downloads[], failures[])
    #       file: url网页保存的文件名
    #       downloads[]: 网页内的链接所对应的文件保存的文件名
    #       failures[]: 下载失败的url列表
    def article_downloaded(self, request, result):
        file_name, downloads, failures = result
        index = os.path.join(os.path.dirname(file_name), 'index.html')
        if index != file_name:
            self.fs.rename(file_name, index)
        
        article = request.article
        self.log.debug('Downloaded article:', article.title, 'from', article.url)
        article.orig_url = article.url
        article.url = f'article_{request.requestID[1]}/index.html'
        article.downloaded = True
        article.sub_pages  = downloads[1:]
        self.jobs_done += 1
        if failures:
            self.partial_failures.append((request.feed.title, article.title, article.url, failures))

    def error_in_article_download(self, request, traceback):
        self.jobs_done += 1
        if traceback and re.search('^AbortArticle:', traceback, flags=re.M) is not None:
            self.log.warn('Aborted download of article: {} from {}'.format(request.article.title, request.article.url))
            self.aborted_articles.append((request.feed, request.article))
        else:
            self.log.error('Failed to download article:{} from {}'.format(request.article.title, request.article.url))
            self.log.debug(traceback)
            self.log.debug('\n')
            self.failed_downloads.append((request.feed, request.article, traceback))

    #从recipe里面定义的feed列表返回一个Feed实例列表
    #Feed类定义在 calibre\web\feeds\__init__.py
    def parse_feeds(self):
        '''
        Create a list of articles from the list of feeds returned by :meth:`BasicNewsRecipe.get_feeds`.
        Return a list of :class:`Feed` objects.
        '''
        feeds = self.get_feeds()
        if not feeds:
            self.log.warning(f'There are no feeds in "{self.title}"')
            return []
        
        parsed_feeds = []
        br = self.browser
        for obj in feeds:
            if isinstance(obj, string_or_bytes):
                title, url = None, obj
            else:
                title, url = obj
            if isinstance(title, bytes):
                title = title.decode('utf-8')
            if isinstance(url, bytes):
                url = url.decode('utf-8')
            if url.startswith('feed://'):
                url = 'http'+url[4:]
            try:
                #purl = urlparse(url, allow_fragments=False)
                #if purl.username or purl.password:
                #    hostname = purl.hostname
                #    if purl.port:
                #        hostname += f':{purl.port}'
                #    url = purl._replace(netloc=hostname).geturl()
                #    if purl.username and purl.password:
                #        br.add_password(url, purl.username, purl.password)
                resp = br.open(url, timeout=self.timeout)
                if resp.status_code == 200:
                    #https://github.com/kurtmckee/feedparser/issues/440
                    #等这个bug解决掉之后可以去掉replace
                    raw = resp.content.replace(b'&lt;![CDATA[', b'<![CDATA[').replace(b']]&gt;', b']]>')
                    pFunc = feed_from_json if raw and raw[0] == b'{' else feed_from_xml
                    feed = pFunc(raw, title=title, log=self.log, oldest_article=self.oldest_article,
                            max_articles_per_feed=self.max_articles_per_feed, get_article_url=self.get_article_url)
                    parsed_feeds.append(feed)
                else:
                    raise Exception(f'Cannot fetch {url}:{resp.status_code}')
            except Exception as e:
                msg = loc_exc_pos('Failed feed: {}'.format(title if title else url))
                self.log.warning(msg)
                feed = Feed() #创建一个空的Feed返回
                feed.populate_from_preparsed_feed(msg, [])
                feed.description = str(e)
                parsed_feeds.append(feed)
                
            delay = self.get_url_specific_delay(url)
            if delay > 0:
                time.sleep(delay)

        remove = [fl for fl in parsed_feeds if len(fl) == 0 and self.remove_empty_feeds]
        for f in remove:
            parsed_feeds.remove(f)
        
        return parsed_feeds

    @classmethod
    def tag_to_string(self, tag, use_alt=True, normalize_whitespace=True):
        '''
        Convenience method to take a
        `BeautifulSoup <https://www.crummy.com/software/BeautifulSoup/bs4/doc/>`_
        :code:`Tag` and extract the text from it recursively, including any CDATA sections
        and alt tag attributes. Return a possibly empty Unicode string.

        `use_alt`: If `True` try to use the alt attribute for tags that don't
        have any textual content

        `tag`: `BeautifulSoup <https://www.crummy.com/software/BeautifulSoup/bs4/doc/>`_
        :code:`Tag`
        '''
        if tag is None:
            return ''
        if isinstance(tag, string_or_bytes):
            return tag
        if callable(getattr(tag, 'xpath', None)) and not hasattr(tag, 'contents'):  # a lxml tag
            from lxml.etree import tostring
            ans = tostring(tag, method='text', encoding='unicode', with_tail=False)
        else:
            strings = []
            for item in tag.contents:
                if isinstance(item, (NavigableString, CData)):
                    strings.append(item.string)
                elif isinstance(item, Tag):
                    res = self.tag_to_string(item)
                    if res:
                        strings.append(res)
                    elif use_alt:
                        try:
                            strings.append(item['alt'])
                        except KeyError:
                            pass
            ans = ''.join(strings)
        if normalize_whitespace:
            ans = re.sub(r'\s+', ' ', ans)
        return ans

    @classmethod
    def soup(cls, raw):
        return BeautifulSoup(raw, 'lxml')

    @classmethod
    def adeify_images(cls, soup):
        '''
        If your recipe when converted to EPUB has problems with images when
        viewed in Adobe Digital Editions, call this method from within
        :meth:`postprocess_html`.
        '''
        for item in soup.findAll('img'):
            for attrib in ['height','width','border','align','style']:
                try:
                    del item[attrib]
                except KeyError:
                    pass
            oldParent = item.parent
            myIndex = oldParent.contents.index(item)
            item.extract()
            divtag = soup.new_tag('div')
            brtag  = soup.new_tag('br')
            oldParent.insert(myIndex,divtag)
            divtag.append(item)
            divtag.append(brtag)
        return soup

    def internal_postprocess_book(self, oeb, opts, log):
        if self.resolve_internal_links and self.article_url_map:
            seen = set()
            for item in oeb.spine:
                for a in item.data.xpath('//*[local-name()="a" and @href]'):
                    if a.get('rel') == 'calibre-downloaded-from':
                        continue
                    url = a.get('href')
                    for curl in self.canonicalize_internal_url(url):
                        articles = self.article_url_map.get(curl)
                        if articles:
                            arelpath = sorted(articles)[0]
                            a.set('href', item.relhref(arelpath))
                            if url not in seen:
                                log.debug(f'Resolved internal URL: {url} -> {arelpath}')
                                seen.add(url)

    #调用在线翻译服务平台，翻译html
    def translate_html(self, soup, title):
        from ebook_translator import HtmlTranslator
        translator = HtmlTranslator(self.translator, self.simultaneous_downloads)
        self.log.info(f'Translating html [{title}]')
        translator.translate_soup(soup)

    #翻译Feed的title，toc时用到
    def translate_titles(self, feeds):
        from ebook_translator import HtmlTranslator
        translator = HtmlTranslator(self.translator, self.simultaneous_downloads)
        position = self.translator.get('position', 'below')
        titles = []
        for feed in feeds:
            titles.append({'text': feed.title, 'obj': feed})
            for article in feed:
                titles.append({'text': article.title, 'obj': article})
        newTitles = translator.translate_text(titles)
        for item in [e for e in newTitles if not e['error']]:
            if position in ('below', 'right'):
                item['obj'].title = item['text'] + ' ' + item['translated']
            elif position in ('above', 'left'):
                item['obj'].title = item['translated'] + ' ' + item['text']
            else: #replace
                item['obj'].title = item['translated']

    #调用在线TTS服务平台，将html转为语音
    #每个音频片段都会调用一次callback(audioDict, title, feed_index, article_index)
    def audiofy_html(self, soup, title, job_info):
        from ebook_tts import HtmlAudiolator
        audiolator = HtmlAudiolator(self.tts)
        self.log.info(f'Audiofying html [{title}]')
        ret = audiolator.audiofy_soup(soup)
        if not ret['error']: #保存音频到磁盘，这个地方就不能使用fs了，因为最后合并mp3时无法使用虚拟文件系统
            if not self.tts.get('audio_dir'):
                system_temp_dir = os.environ.get('KE_TEMP_DIR')
                self.tts['audio_dir'] = PersistentTemporaryDirectory(prefix='tts_', dir=system_temp_dir)
            if not self.tts.get('audio_files'):
                self.tts['audio_files'] = []
            audio_dir = self.tts['audio_dir']
            ext = ret['mime'].split('/')[-1]
            ext = {'mpeg': 'mp3'}.get(ext, ext)
            for idx, audio in enumerate(ret['audios']):
                filename = f'{job_info.f_idx:03d}_{job_info.a_idx:03d}_{idx:04d}.{ext}'
                filename = os.path.join(audio_dir, filename)
                try:
                    with open(filename, 'wb') as f:
                        f.write(audio)
                    self.tts['audio_files'].append(filename)
                except Exception as e:
                    self.log.warning(f'Failed to write "{filename}": {e}')
        else:
            self.log.warning(f'Failed to audiofy "{title}": {ret["error"]}')

class CustomIndexRecipe(BasicNewsRecipe):

    def custom_index(self):
        '''
        Return the filesystem path to a custom HTML document that will serve as the index for
        this recipe. The index document will typically contain many `<a href="...">`
        tags that point to resources on the internet that should be downloaded.
        '''
        raise NotImplementedError

    def create_opf(self):
        mi = MetaInformation(self.title + strftime(self.timefmt), [__appname__])
        mi.publisher = __appname__
        mi.author_sort = __appname__
        mi = OPFCreator(self.output_dir, mi)
        mi.create_manifest_from_files_in([self.output_dir])
        mi.create_spine([os.path.join(self.output_dir, 'index.html')])
        opf_file = io.BytesIO()
        mi.render(opf_file)
        self.fs.write(os.path.join(self.output_dir, 'index.opf'), opf_file.getvalue(), 'wb')

    def download(self):
        index = self.custom_index()
        url = 'file:'+index if iswindows else 'file://'+index
        self.web2disk_options.browser = self.clone_browser(self.browser)
        fetcher = RecursiveFetcher(self.web2disk_options, self.fs, self.log)
        fetcher.base_dir = self.output_dir
        fetcher.current_dir = self.output_dir
        fetcher.show_progress = False
        res = fetcher.start_fetch(url)
        #self.create_opf()
        return res


class AutomaticNewsRecipe(BasicNewsRecipe):
    auto_cleanup = True

#保存的url为网页url，而不是RSS/ATOM
class UrlNewsRecipe(BasicNewsRecipe):
    auto_cleanup = True

    #返回一个Feed实例列表
    def parse_feeds(self):
        urls = self.get_feeds()
        if not urls:
            self.log.warning(f'There are no urls in "{self.title}"')
            return []
        
        feed = Feed()
        feed.title = self.title
        feed.description = ''
        feed.image_url = None
        feed.oldest_article = self.oldest_article
        feed.articles = []
        id_counter = 0
        now = time.gmtime()
        for obj in urls:
            title, url = (self.title, obj) if isinstance(obj, str) else obj
            id_counter += 1
            feed.articles.append(Article(f'internal id#{id_counter}', title, url, 'KindleEar', '', now, ''))
        feed.id_counter = id_counter

        return [feed]


#保存的url为网页url，给定一个规则，从网页url里面提取链接，每个链接一篇文章
#一般用于新闻类的网页，即使新闻网站不提供RSS，也可以每天去获取新闻
#这个类建议搭配KindleEar chrome插件使用，插件可以自动生成抓取脚本
class WebPageUrlNewsRecipe(BasicNewsRecipe):
    max_articles_per_feed = 30

    #为一个二维列表，可以保存多个标签规则，每个规则都很灵活，只要是BeautifulSoup的合法规则即可(字典或CSS选择器字符串)
    #每个顶层元素为一个html标签的查找规则列表，从父节点到子节点，依次往下一直到最后一个元素为止
    #最后一个元素必须为链接，或其子节点有链接，则此链接为文章最终链接，链接的文本为文章标题
    #比如：url_extract_rules = [[{'name': 'div', 'attrs': {'class': 'art', 'data': True}}, {'name': 'a'}],]
    #或:url_extract_rules = [['div.art[data]', 'a'],]
    url_extract_rules = []

    #格式和 url_extract_rules 一致，在文章的网页中提取文章正文，为空则使用自动提取
    content_extract_rules = []

    #格式和 url_extract_rules 一致，在提取正文后再删除部分不需要的内容
    content_remove_rules = []

    #返回一个Feed实例列表
    def parse_feeds(self):
        if not self.url_extract_rules:
            return super().parse_feeds()
            
        main_urls = self.get_feeds()
        if not main_urls:
            self.log.warning(f'There are no urls in "{self.title}"')
            return []
        
        feeds = []
        id_counter = 0
        added = set()
        #这里oldest_article和其他的recipe不一样，这个参数表示在这个区间内不会重复推送
        oldestSeconds = 24 * 3600 * self.oldest_article
        now = datetime.datetime.utcnow()
        for obj in main_urls: #type:ignore
            main_title, main_url = (self.title, obj) if isinstance(obj, str) else obj
            feed = Feed()
            feed.title = main_title
            feed.description = ''
            feed.image_url = None
            feed.oldest_article = self.oldest_article
            feed.articles = []
            
            for title, url in self.extract_urls(main_title, main_url):
                if len(feed) >= self.max_articles_per_feed:
                    break
                if url in added: #避免重复添加
                    continue

                added.add(url)
                timeItem = LastDelivered.get_or_none((LastDelivered.user==self.user.name) & 
                    (LastDelivered.bookname==self.title) & (LastDelivered.url==url))
                delta = (now - timeItem.datetime).total_seconds() if timeItem else (oldestSeconds + 1)
                if (self.delivery_reason == 'manual') or (delta > oldestSeconds):
                    id_counter += 1
                    feed.articles.append(Article(f'internal id#{id_counter}', title, url, 'KindleEar', 
                        '', time.gmtime(), ''))

                    #如果是手动推送，不单不记录已推送日期，还将已有的上次推送日期数据删除
                    if timeItem and ((self.delivery_reason == 'manual') or (not oldestSeconds)):
                        timeItem.delete_instance()
                    elif not timeItem:
                        LastDelivered.create(user=self.user.name, bookname=self.title, url=url)
                else:
                    self.log.debug(f'Skipping article {title}({url}) as it is too old.')

            feed.id_counter = id_counter
            if len(feed) > 0:
                feeds.append(feed)

        return feeds

    #从一个网页中根据指定的规则，提取文章链接
    def extract_urls(self, main_title, main_url):
        resp = self.browser.open(main_url, timeout=self.timeout)
        if resp.status_code != 200:
            self.log.warning(f'Failed to fetch {main_url}: {UrlOpener.CodeMap(resp.status_code)}')
            return []

        soup = BeautifulSoup(resp.text, 'lxml')
        
        articles = []
        for rules in self.url_extract_rules:
            for item in get_tags_from_rules(soup, rules):
                #如果最终tag不是链接，则在子节点中查找，并且添加所有找到的链接
                item = item.find_all('a') if item.name.lower() != 'a' else [item]
                for tag in item:
                    title = ' '.join(tag.stripped_strings) or main_title
                    url = tag.attrs.get('href', None)
                    if not url.startswith('http'):
                        url = urljoin(main_url, url)
                    if title and url:
                        articles.append((title, url))

        self.log.debug(f'Found {len(articles)} articles in {self.title}\n')
        self.log.debug(str(articles))
        return articles

    #提取文章内容，这个函数在文章被下载解码为unicode后，转换为DOM树前被调用
    def preprocess_raw_html(self, raw_html, url):
        if self.auto_cleanup or not self.content_extract_rules: #由readability自动提取
            return raw_html

        soup = BeautifulSoup(raw_html, 'lxml')
        oldBody = soup.find('body')
        if not oldBody:
            return raw_html

        newBody = soup.new_tag('body')
        for rules in self.content_extract_rules:
            newBody.extend(get_tags_from_rules(soup, rules))
        oldBody.replace_with(newBody)
        for rules in self.content_remove_rules:
            remove_tags_from_rules(soup, rules)
            
        #提取失败，尝试自动提取
        if len(newBody.get_text(strip=True)) < 200:
            self.log.warning(f'Failed to extract content using content_extract_rules, try readability algorithm: {url}')
            try:
                raw_html = self.extract_readable_article(raw_html, url)
            except:
                self.log.warning(f'Failed to auto cleanup URL: {url}')
            return raw_html
        else:
            return str(soup)

class CalibrePeriodical(BasicNewsRecipe):

    #: Set this to the slug for the calibre periodical
    calibre_periodicals_slug = None

    LOG_IN = 'https://news.calibre-ebook.com/accounts/login'
    needs_subscription = True
    __author__ = 'calibre Periodicals'

    def get_browser(self):
        br = BasicNewsRecipe.get_browser(self)
        br.open(self.LOG_IN)
        br.select_form(name='login')
        br['username'] = self.username
        br['password'] = self.password
        raw = br.submit_selected().content
        if 'href="/my-account"' not in raw:
            raise LoginFailed(
                    _('Failed to log in, check your username and password for'
                    ' the calibre Periodicals service.'))

        return br
    get_browser.is_base_class_implementation = True

    def download(self):
        self.log('Fetching downloaded recipe')
        try:
            raw = self.browser.open_novisit(
                'https://news.calibre-ebook.com/subscribed_files/%s/0/temp.downloaded_recipe'
                % self.calibre_periodicals_slug
                    ).read()
        except Exception as e:
            if hasattr(e, 'getcode') and e.getcode() == 403:
                raise DownloadDenied(
                        _('You do not have permission to download this issue.'
                        ' Either your subscription has expired or you have'
                        ' exceeded the maximum allowed downloads for today.'))
            raise
        f = io.BytesIO(raw)
        from calibre.utils.zipfile import ZipFile
        zf = ZipFile(f)
        zf.extractall()
        zf.close()
        from glob import glob

        from calibre.web.feeds.recipes import compile_recipe
        try:
            recipe = compile_recipe(open(glob('*.recipe')[0],
                'rb').read())
            self.conversion_options = recipe.conversion_options
        except:
            self.log.exception('Failed to compile downloaded recipe')
        return os.path.abspath('index.html')

#下载url对应的html和其内部的图像文件
#fs: FsDictStub 对象
def recursive_fetch_url(url: str, fs):
    wOpts = Web2diskOptions()
    wOpts.browser = UrlOpener(file_stub=fs)
    wOpts.dir = fs.path
    image_map = {}
    css_map = {}
    fetcher = RecursiveFetcher(wOpts, fs, default_log, None, image_map, css_map)
    
    #res为对应url的一个html文件名
    res = fetcher.start_fetch(url)
    paths = fetcher.downloaded_paths
    failures = fetcher.failed_links
    return res, paths, failures

#根据一个规则列表，从soup中获取符合条件的tag列表
#rules: 字符串列表或字典列表
#返回tag列表
def get_tags_from_rules(soup, rules):
    if isinstance(rules[0], dict): #使用Tag字典查找
        resultTags = soup.find_all(**rules[0])
        for idx, flt in enumerate(rules[1:]):
            resultTags = [tag.find_all(**flt) for tag in resultTags]
            resultTags = [tag for sublist in resultTags for tag in sublist] #二级列表展开为一级列表
    else: #使用CSS选择器，每个选择器的总共最长允许字符长度：1366
        resultTags = soup.select(' '.join(rules))
    return resultTags

#根据一个规则列表，从soup中去除符合条件的tag列表
#rules: 字符串列表或字典列表
#此函数直接在soup上修改
def remove_tags_from_rules(soup, rules):
    resultTags = []
    if isinstance(rules[0], dict): #使用Tag字典查找
        resultTags = soup.find_all(**rules[0])
        for idx, flt in enumerate(rules[1:]):
            resultTags = [tag.find_all(**flt) for tag in resultTags]
            resultTags = [tag for sublist in resultTags for tag in sublist] #二级列表展开为一级列表
    else: #使用CSS选择器，每个选择器的总共最长允许字符长度：1366
        resultTags = list(soup.select(' '.join(rules)))

    for tag in resultTags:
        tag.extract()