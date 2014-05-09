# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from itertools import izip

from calibre.customize import Plugin as _Plugin

FONT_SIZES = [('xx-small', 1),
              ('x-small',  None),
              ('small',    2),
              ('medium',   3),
              ('large',    4),
              ('x-large',  5),
              ('xx-large', 6),
              (None,       7)]


class Plugin(_Plugin):

    fbase  = 12
    fsizes = [5, 7, 9, 12, 13.5, 17, 20, 22, 24]
    screen_size = (1600, 1200)
    dpi = 100

    def __init__(self, *args, **kwargs):
        _Plugin.__init__(self, *args, **kwargs)
        self.width, self.height = self.screen_size
        fsizes = list(self.fsizes)
        self.fkey = list(self.fsizes)
        self.fsizes = []
        for (name, num), size in izip(FONT_SIZES, fsizes):
            self.fsizes.append((name, num, float(size)))
        self.fnames = dict((name, sz) for name, _, sz in self.fsizes if name)
        self.fnums = dict((num, sz) for _, num, sz in self.fsizes if num)
        self.width_pts = self.width * 72./self.dpi
        self.height_pts = self.height * 72./self.dpi

# Input profiles {{{
class InputProfile(Plugin):

    author = 'Kovid Goyal'
    supported_platforms = set(['windows', 'osx', 'linux'])
    can_be_disabled = False
    type = _('Input profile')

    name        = 'Default Input Profile'
    short_name  = 'default' # Used in the CLI so dont use spaces etc. in it
    description = _('This profile tries to provide sane defaults and is useful '
                    'if you know nothing about the input document.')


class SonyReaderInput(InputProfile):

    name        = 'Sony Reader'
    short_name  = 'sony'
    description = _('This profile is intended for the SONY PRS line. '
                    'The 500/505/600/700 etc.')

    screen_size               = (584, 754)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class MobipocketInput(InputProfile):

    name        = 'Mobipocket Books'
    short_name  = 'mobipocket'
    description = _('This profile is intended for the Mobipocket books.')

    # Unfortunately MOBI books are not narrowly targeted, so this information is
    # quite likely to be spurious
    screen_size               = (600, 800)
    dpi                       = 96
    fbase                     = 18
    fsizes                    = [14, 14, 16, 18, 20, 22, 24, 26]

class KindleInput(InputProfile):

    name        = 'Kindle'
    short_name  = 'kindle'
    description = _('This profile is intended for the Amazon Kindle.')

    # Screen size is a best guess
    screen_size               = (525, 640)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class NookInput(InputProfile):

    author      = 'John Schember'
    name        = 'Nook'
    short_name  = 'nook'
    description = _('This profile is intended for the B&N Nook.')

    # Screen size is a best guess
    screen_size               = (600, 800)
    dpi                       = 167
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

#input_profiles = [InputProfile, SonyReaderInput, SonyReader300Input,
#        SonyReader900Input, MSReaderInput, MobipocketInput, HanlinV3Input,
#        HanlinV5Input, CybookG3Input, CybookOpusInput, KindleInput, IlliadInput,
#        IRexDR1000Input, IRexDR800Input, NookInput]
input_profiles = [KindleInput,]

#input_profiles.sort(cmp=lambda x,y:cmp(x.name.lower(), y.name.lower()))

# }}}

class OutputProfile(Plugin):

    author = 'Kovid Goyal'
    supported_platforms = set(['windows', 'osx', 'linux'])
    can_be_disabled = False
    type = _('Output profile')

    name        = 'Default Output Profile'
    short_name  = 'default' # Used in the CLI so dont use spaces etc. in it
    description = _('This profile tries to provide sane defaults and is useful '
                    'if you want to produce a document intended to be read at a '
                    'computer or on a range of devices.')

    #: The image size for comics
    comic_screen_size = (584, 754)

    #: If True the MOBI renderer on the device supports MOBI indexing
    supports_mobi_indexing = False

    #: If True output should be optimized for a touchscreen interface
    touchscreen = False
    touchscreen_news_css = ''
    #: A list of extra (beyond CSS 2.1) modules supported by the device
    #: Format is a cssutils profile dictionary (see iPad for example)
    extra_css_modules = []
    #: If True, the date is appended to the title of downloaded news
    periodical_date_in_title = True

    #: Characters used in jackets and catalogs
    ratings_char = u'*'
    empty_ratings_char = u' '

    #: Unsupported unicode characters to be replaced during preprocessing
    unsupported_unicode_chars = []

    #: Number of ems that the left margin of a blockquote is rendered as
    mobi_ems_per_blockquote = 1.0

    #: Special periodical formatting needed in EPUB
    epub_periodical_format = None

    @classmethod
    def tags_to_string(cls, tags):
        from xml.sax.saxutils import escape
        return escape(', '.join(tags))

class SonyReaderOutput(OutputProfile):

    name        = 'Sony Reader'
    short_name  = 'sony'
    description = _('This profile is intended for the SONY PRS line. '
                    'The 500/505/600/700 etc.')

    screen_size               = (590, 775)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]
    unsupported_unicode_chars = [u'\u201f', u'\u201b']

    epub_periodical_format = 'sony'
    #periodical_date_in_title = False


class KoboReaderOutput(OutputProfile):

    name = 'Kobo Reader'
    short_name = 'kobo'

    description = _('This profile is intended for the Kobo Reader.')

    screen_size               = (536, 710)
    comic_screen_size         = (536, 710)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class MobipocketOutput(OutputProfile):

    name        = 'Mobipocket Books'
    short_name  = 'mobipocket'
    description = _('This profile is intended for the Mobipocket books.')

    # Unfortunately MOBI books are not narrowly targeted, so this information is
    # quite likely to be spurious
    screen_size               = (600, 800)
    dpi                       = 96
    fbase                     = 18
    fsizes                    = [14, 14, 16, 18, 20, 22, 24, 26]

class KindleOutput(OutputProfile):

    name        = 'Kindle'
    short_name  = 'kindle'
    description = _('This profile is intended for the Amazon Kindle.')

    # Screen size is a best guess
    screen_size               = (525, 640)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]
    supports_mobi_indexing = True
    periodical_date_in_title = False

    empty_ratings_char = u'\u2606'
    ratings_char = u'\u2605'

    mobi_ems_per_blockquote = 2.0

    @classmethod
    def tags_to_string(cls, tags):
        return u'%s <br/><span style="color:white">%s</span>' % (', '.join(tags),
                'ttt '.join(tags)+'ttt ')

class KindleDXOutput(OutputProfile):

    name        = 'Kindle DX'
    short_name  = 'kindle_dx'
    description = _('This profile is intended for the Amazon Kindle DX.')

    # Screen size is a best guess
    screen_size               = (744, 1022)
    dpi                       = 150.0
    comic_screen_size = (771, 1116)
    #comic_screen_size         = (741, 1022)
    supports_mobi_indexing = True
    periodical_date_in_title = False
    empty_ratings_char = u'\u2606'
    ratings_char = u'\u2605'
    mobi_ems_per_blockquote = 2.0

    @classmethod
    def tags_to_string(cls, tags):
        return u'%s <br/><span style="color: white">%s</span>' % (', '.join(tags),
                'ttt '.join(tags)+'ttt ')

class KindlePaperWhiteOutput(KindleOutput):

    name = 'Kindle PaperWhite'
    short_name = 'kindle_pw'
    description = _('This profile is intended for the Amazon Kindle PaperWhite')

    # Screen size is a best guess
    screen_size               = (658, 940)
    dpi                       = 212.0
    comic_screen_size = screen_size

class KindleFireOutput(KindleDXOutput):

    name = 'Kindle Fire'
    short_name = 'kindle_fire'
    description = _('This profile is intended for the Amazon Kindle Fire.')

    screen_size               = (570, 1016)
    dpi                       = 169.0
    comic_screen_size = (570, 1016)

    @classmethod
    def tags_to_string(cls, tags):
        # The idiotic fire doesn't obey the color:white directive
        from xml.sax.saxutils import escape
        return escape(', '.join(tags))


class NookOutput(OutputProfile):

    author      = 'John Schember'
    name        = 'Nook'
    short_name  = 'nook'
    description = _('This profile is intended for the B&N Nook.')

    # Screen size is a best guess
    screen_size               = (600, 730)
    comic_screen_size         = (584, 730)
    dpi                       = 167
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class NookColorOutput(NookOutput):
    name = 'Nook Color'
    short_name = 'nook_color'
    description = _('This profile is intended for the B&N Nook Color.')

    screen_size               = (600, 900)
    comic_screen_size         = (594, 900)
    dpi                       = 169


#output_profiles = [OutputProfile, SonyReaderOutput, SonyReader300Output,
#        SonyReader900Output, MSReaderOutput, MobipocketOutput, HanlinV3Output,
#        HanlinV5Output, CybookG3Output, CybookOpusOutput, KindleOutput,
#        iPadOutput, iPad3Output, KoboReaderOutput, TabletOutput, SamsungGalaxy,
#        SonyReaderLandscapeOutput, KindleDXOutput, IlliadOutput, NookHD,
#        IRexDR1000Output, IRexDR800Output, JetBook5Output, NookOutput,
#        BambookOutput, NookColorOutput, PocketBook900Output, PocketBookPro912Output,
#        GenericEink, GenericEinkLarge, KindleFireOutput, KindlePaperWhiteOutput]
output_profiles = [KindleOutput,]
#output_profiles.sort(cmp=lambda x,y:cmp(x.name.lower(), y.name.lower()))
