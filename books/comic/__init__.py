import itertools

from .cartoonmadbase import CartoonMadBaseBook
from .tencentbase import TencentBaseBook
from .manhuaguibase import ManHuaGuiBaseBook
from .manhuarenbase import ManHuaRenBaseBook
from .seven33sobase import Seven33SoBaseBook
from .tohomhbase import ToHoMHBaseBook
from .dmzjbase import DMZJBaseBook

ComicBaseClasses = [
    CartoonMadBaseBook,
    TencentBaseBook,
    ManHuaGuiBaseBook,
    ManHuaRenBaseBook,
    Seven33SoBaseBook,
    ToHoMHBaseBook,
    DMZJBaseBook,
]

comic_domains = tuple(itertools.chain(*[x.accept_domains for x in ComicBaseClasses]))
