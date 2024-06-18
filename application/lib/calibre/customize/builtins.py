__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.customize import MetadataWriterPlugin

class EPUBMetadataWriter(MetadataWriterPlugin):

    name = 'Set EPUB metadata'
    file_types = {'epub'}
    description = _('Set metadata in %s files')%'EPUB'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.epub import set_metadata
        q = self.site_customization or ''
        set_metadata(stream, mi, apply_null=self.apply_null, force_identifiers=self.force_identifiers, add_missing_cover='disable-add-missing-cover' != q)

    def customization_help(self, gui=False):
        h = 'disable-add-missing-cover'
        if gui:
            h = '<i>' + h + '</i>'
        return _('Enter {0} below to have the EPUB metadata writer plugin not'
                 ' add cover images to EPUB files that have no existing cover image.').format(h)

class MOBIMetadataWriter(MetadataWriterPlugin):

    name        = 'Set MOBI metadata'
    file_types  = {'mobi', 'prc', 'azw', 'azw3', 'azw4'}
    description = _('Set metadata in %s files')%'MOBI'
    author      = 'Marshall T. Vandegrift'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.mobi import set_metadata
        set_metadata(stream, mi)

from calibre.ebooks.conversion.plugins.recipe_input import RecipeInput
from calibre.ebooks.conversion.plugins.html_input import HTMLInput
from calibre.ebooks.conversion.plugins.epub_input import EPUBInput
from calibre.ebooks.conversion.plugins.epub_output import EPUBOutput
from calibre.ebooks.conversion.plugins.mobi_input import MOBIInput
from calibre.ebooks.conversion.plugins.mobi_output import (MOBIOutput, AZW3Output)
from calibre.ebooks.conversion.plugins.oeb_output import OEBOutput

plugins = [RecipeInput, HTMLInput, MOBIInput, EPUBOutput, MOBIOutput, AZW3Output, OEBOutput, EPUBMetadataWriter, MOBIMetadataWriter]

from calibre.customize.profiles import input_profiles, output_profiles
plugins += input_profiles
plugins += output_profiles
