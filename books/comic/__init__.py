import itertools

from .cartoonmadbase import CartoonMadBaseBook
from .tencentbase import TencentBaseBook
from .manhuaguibase import ManHuaGuiBaseBook
from .seven33sobase import Seven33SoBaseBook
from .tohomhbase import ToHoMHBaseBook

ComicBaseClasses = [
    CartoonMadBaseBook,
    TencentBaseBook,
    ManHuaGuiBaseBook,
    Seven33SoBaseBook,
    ToHoMHBaseBook,
]

comic_domains = tuple(itertools.chain(*[x.accept_domains for x in ComicBaseClasses]))
