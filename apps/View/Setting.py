#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#设置页面

from bottle import route, pos, redirect, request
from apps.base_handler import *
from apps.db_models import *
from config import *

#各种语言的语种代码和文字描述的对应关系
def LangMap(): 
    return {"zh-cn": _("Chinese"),
        "en-us": _("English"),
        "fr-fr": _("French"),
        "es-es": _("Spanish"),
        "pt-br": _("Portuguese"),
        "de-de": _("German"),
        "it-it": _("Italian"),
        "ja-jp": _("Japanese"),
        "ru-ru": _("Russian"),
        "tr-tr": _("Turkish"),
        "ko-kr": _("Korean"),
        "ar": _("Arabic"),
        "cs": _("Czech"),
        "nl": _("Dutch"),
        "el": _("Greek"),
        "hi": _("Hindi"),
        "ms": _("Malaysian"),
        "bn": _("Bengali"),
        "fa": _("Persian"),
        "ur": _("Urdu"),
        "sw": _("Swahili"),
        "vi": _("Vietnamese"),
        "pa": _("Punjabi"),
        "jv": _("Javanese"),
        "tl": _("Tagalog"),
        "ha": _("Hausa"),}

@route("/setting")
def Setting(self, tips=None):
    user = get_current_user()
    if not user.own_feeds.language:
        user.own_feeds.language = "zh-cn"

    return render_page('setting.html', "Settings",
        current='setting', user=user, mail_sender=SRC_EMAIL, tips=tips, lang_map=LangMap())

@post("/setting")
def SettingPost():
    user = get_current_user()
    forms = request.forms
    keMail = forms.kindleemail
    myTitle = forms.rt
    sgEnable = bool(forms.get('sgenable'))
    sgApikey = forms.sgapikey
    if not keMail:
        tips = _("Kindle E-mail is requied!")
    elif not myTitle:
        tips = _("Title is requied!")
    elif sgEnable and (not sgApikey):
        tips = _("Need sendgrid ApiKey!")
    else:
        user.kindle_email = keMail.strip(';, ')
        user.timezone = int(forms.get('timezone', TIMEZONE))
        user.send_time = int(forms.get('sendtime', '0'))
        user.enable_send = bool(forms.get('enablesend'))
        user.book_type = forms.get('booktype', 'epub')
        user.device = forms.get('devicetype', 'kindle')
        user.use_title_in_feed = bool(forms.titlefrom == 'feed')
        user.titlefmt = forms.titlefmt
        alldays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        user.send_days = [day for day in alldays if forms.get(day)]
        user.merge_books = bool(forms.get('mergebooks'))
        user.book_mode = forms.bookmode
        user.remove_hyperlinks = forms.removehyperlinks
        user.author_format = forms.authorformat
        user.sg_enable = sgEnable
        user.sg_apikey = sgApikey
        user.put()

        myfeeds = user.own_feeds
        myfeeds.language = forms.get("lng", "en-us")
        myfeeds.title = myTitle
        myfeeds.keep_image = bool(forms.get("keepimage"))
        myfeeds.oldest_article = int(forms.get('oldest', 7))
        myfeeds.users = [user.name] if forms.enablerss else []
        myfeeds.put()
        tips = _("Settings Saved!")

    return render_page('setting.html', "Settings",
        current='setting', user=user, mail_sender=SRC_EMAIL, tips=tips, lang_map=LangMap())

@route("/lang/<lang>")
def SetLang(lang):
    global supported_languages
    session = current_session()
    lang = lang.lower()
    if lang not in supported_languages:
        return "language invalid!"
    session.lang = lang
    session.save()
    redirect('/')

