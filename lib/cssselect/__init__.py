# coding: utf8
"""
    CSS Selectors based on XPath
    ============================

    This module supports selecting XML/HTML elements based on CSS selectors.
    See the `CSSSelector` class for details.


    :copyright: (c) 2007-2012 Ian Bicking and contributors.
                See AUTHORS for more details.
    :license: BSD, see LICENSE for more details.

"""

from cssselect.parser import (parse, Selector, SelectorError,
                              SelectorSyntaxError)
from cssselect.xpath import GenericTranslator, HTMLTranslator, ExpressionError


VERSION = '0.8'
__version__ = VERSION
