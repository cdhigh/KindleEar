
//所有的分享RSS数据
var g_SharedRss = false;
//分语言种类
var g_rssByLang = {};
//由BuildSharedRssByCategory()根据搜索词动态更新此数组
var g_rssByCat = [];

//将一个数组打乱，返回原数组
function shuffleArray(array) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    let temp = array[i];
    array[i] = array[j];
    array[j] = temp;
  }
  return array;
}

//排序网友分享库的RSS，先按流行程度（订阅数）倒序，订阅数相同的按时间倒序
function SortSharedRssDataArray() {
  if (!g_SharedRss) {
    return;
  }

  g_SharedRss.sort(function(a, b) {
    var ret = b.s - a.s; //s:subscribed
    if (ret == 0) {
      ret = b.d - a.d; //d:datetime
    }
    return ret;
  });
  
  //最近被订阅的共享RSS留着置顶位置3天
  var now = getNowSeconds();
  var recent = new Array();
  for (var i = g_SharedRss.length - 1; i >= 0; i--) {
    if (Math.abs(now - g_SharedRss[i].d) < 60 * 60 * 24 * 3) {
      recent.unshift(g_SharedRss.splice(i, 1)[0]);
    }
  }
  for (var i = recent.length - 1; i >= 0; i--) {
    g_SharedRss.unshift(recent[i]);
  }
}

//创建一个按照语言种类分类的字典，字典键为两位语言代码，值为列表
function BuildSharedRssByLang() {
  if (!g_SharedRss) {
    return;
  }
  g_rssByLang = {};
  var userLang = BrowserLanguage();
  var hasUserLangRss = false;
  var hasEnRss = false;
  for (var idx = 0; idx < g_SharedRss.length; idx++) {
    var item = g_SharedRss[idx];
    lang = item.l ? item.l : 'und'; //l=language

    //忽略各国语言方言，仅取'_'前的部分
    lang = lang.replace('-', '_');
    var dashIndex = lang.indexOf('_');
    if (dashIndex != -1) {
      lang = lang.substring(0, dashIndex);
    }
    if (lang == userLang) {
      hasUserLangRss = true;
    }
    if (lang == 'en') {
      hasEnRss = true;
    }
    
    if (!g_rssByLang[lang]) {
      g_rssByLang[lang] = [];
      var $newLangOpt = $('<option value="{0}">{1}</option>'.format(lang, LanguageName(lang)));
      $("#shared_rss_lang_pick").append($newLangOpt);
    }
    g_rssByLang[lang].push(item);
  }
  //自动触发和用户浏览器同样语种的选项
  if (hasUserLangRss) {
    $("#shared_rss_lang_pick").find("option[value='" + userLang + "']").attr("selected", true);
    $("#shared_rss_lang_pick").val(userLang).trigger('change');
  } else if (hasEnRss) { //如果有英语则选择英语源
    $("#shared_rss_lang_pick").find("option[value='en']").attr("selected", true);
    $("#shared_rss_lang_pick").val('en').trigger('change');
  } else { //最后只能选择第一个语言
    var firstChild = $("#shared_rss_lang_pick").children().first();
    firstChild.attr("selected", true);
    firstChild.trigger('change');
  }
}

//在界面上选择了一项Recipe语种，将对应语种的recipe显示出来
$("#shared_rss_lang_pick").on("change", function(){
  DoSearchInShared();
});

//返回特定关键词搜索的综合排序的列表
function GetRssListByText(lang, txt) {
  rss = g_rssByLang[lang];
  if (!rss) {
    return [];
  }

  txt = txt ? txt.toUpperCase() : '';
  var byText = [];
  var title, url;
  for (var i = 0; i < rss.length; i++) {
    title = rss[i].t.toUpperCase();
    url = rss[i].u.toUpperCase();
    if ((title.indexOf(txt) > -1) || (url.indexOf(txt) > -1)) {
      byText.push(rss[i])
    }
  }
  return byText;
}

//返回特定关键词搜索的仅按时间排序的列表
function GetRssListByTime(lang, txt) {
  var byTextTime = GetRssListByText(lang, txt);
  byTextTime.sort(function(a, b) {
    return b.d - a.d;
  });
  return byTextTime;
}

//返回特定关键词搜索的随机排序的列表
function GetRssShuffledListByText(lang, txt) {
  rss = g_rssByLang[lang];
  if (!rss) {
    return [];
  }

  txt = txt ? txt.toUpperCase() : '';
  var byText = [];
  var title, url;
  for (var i = 0; i < rss.length; i++) {
    title = rss[i].t.toUpperCase();
    url = rss[i].u.toUpperCase();
    if ((title.indexOf(txt) > -1) || (url.indexOf(txt) > -1)) {
      byText.push(rss[i])
    }
  }

  return shuffleArray(byText);
}

//根据搜索词动态更新此数组 g_rssByCat[]
//lang: 用户选择的语言代码，两位字母
//txt: 搜索词，可以为空
function BuildSharedRssByCategory(lang, txt) {
  var bySearchText = GetRssListByText(lang, txt);
  var byTextTime = GetRssListByTime(lang, txt);
  var byShuffled = GetRssShuffledListByText(lang, txt);

  g_rssByCat = [];
  g_rssByCat[i18n.catAll] = bySearchText;
  g_rssByCat[i18n.catByTime] = byTextTime;
  g_rssByCat[i18n.catRandom] = byShuffled;
  for (var idx = 0; idx < bySearchText.length; idx++) {
    var item = bySearchText[idx];
    var category = item.c || i18n.uncategoried; //c:category
    g_rssByCat[category] = g_rssByCat[category] || [];
    g_rssByCat[category].push(item);
  }
}

//生成左边的分类菜单
function CreateCategoryMenu() {
  var ulNode = $("#ul-category-menu");
  var menuStr = [];
  
  for (var cat in g_rssByCat) {
    menuStr.push('<li class="pure-menu-item"><a href="javascript:;" onclick="SelectCategory(this,\'');
    menuStr.push(cat);
    menuStr.push('\');return false;" class="pure-menu-link category-menu">');
    menuStr.push(cat);
    menuStr.push(' (' + g_rssByCat[cat].length + ')</a></li>');
  }
  
  ulNode.html(menuStr.join(''));
}

//将选中的分类高亮显示
function HightlightCategory(nodeLi) {
  var parentNode = nodeLi.parent();
  var childrenNodes = parentNode.children();
  childrenNodes.removeClass('pure-menu-selected');
  nodeLi.first().addClass('pure-menu-selected');
};

//根据指定条件分页，返回字典 {data:[xx,...], currentPage:1, maxPage:5}
function paginated(category, currentPage, pageSize) {
  var pageSize = pageSize || 30; // for best compatibility
  var ret = {data: [], currentPage: 1, maxPage: 1};
  if (!(category in g_rssByCat)) {
    return ret;
  }

  var rssInThisCat = g_rssByCat[category];
  var maxPage = Math.ceil(rssInThisCat.length / pageSize);
  if (currentPage <= 0) {
    currentPage = 1;
  } else if (currentPage > maxPage){
    currentPage = maxPage;
  }

  if (maxPage <= 1) {
    ret.data = rssInThisCat;
  } else {
    var begin = ((currentPage - 1) * pageSize);
    var end = begin + pageSize;
    ret.data = rssInThisCat.slice(begin, end);
    ret.currentPage = currentPage;
    ret.maxPage = maxPage;
  }
  return ret;
}

//根据选定的页数和分类，创建显示列表，返回html内容
function CreatePageContent(category, page) {
  pageData = paginated(category, page); //返回{data:[], currentPage:, maxPage:}
  if (page <= 0) {
    page = 1;
  } else if (page > pageData.maxPage) {
    page = pageData.maxPage;
  }

  if (pageData.data.length == 0) {
    return '<p style="text-align:center;">' + i18n.noLinksFound + '</p>';
  }

  var rssStr = ['<div class="box-list">'];
  var data = pageData.data;
  var aStr = "";
  var now = getNowSeconds();
    
  for (idx in data){
    var item = data[idx];
    var supText = "";
    //if (Math.abs(now - item.d) < 60 * 60 * 24 * 3) { //3天内分享的rss标识为New
    //    supText = "<sup> New</sup>";
    //}
    rssStr.push('<div class="book box">');
    rssStr.push('<div class="titleRow">' + item.t + supText + '</div>');
    if (item.u) { //url存在说明是自定义rss，否则为上传的recipe
      rssStr.push('<div class="summaryRow"><a target="_blank" href="' + item.u + '">' + item.u + '</a></div>');
    } else {
      rssStr.push('<div class="summaryRow">' + item.e + '</div>'); //e:description
    }

    hamb_arg = [];
    //汉堡按钮弹出菜单代码
    var dbId = item.r || '';
    let title = encodeJsSafeStr(item.t);
    var repAct = "ReportInvalid('{0}','{1}','{2}')".format(title, item.u, dbId);
    var subsAct = "SubscribeSharedFeed('{0}','{1}','{2}','{3}',{4})";
    hamb_arg.push({klass: 'btn-A', title: i18n.invalidReport, icon: 'icon-offcloud', act: repAct});
    hamb_arg.push({klass: 'btn-C', title: i18n.subscriSep, icon: 'icon-push', act: 
      subsAct.format(title, item.u, item.f, dbId, 1)});
    hamb_arg.push({klass: 'btn-D', title: i18n.subscribe, icon: 'icon-subscribe', act: 
      subsAct.format(title, item.u, item.f, dbId, 0)});
    rssStr.push(AddHamburgerButton(hamb_arg)); //AddHamburgerButton()在base.js里
    rssStr.push('</div>');
  }
  rssStr.push('</div>');

  // need pagination?
  if (pageData.maxPage > 1) {
    rssStr.push(GeneratePaginationButtons(category, page, pageData.maxPage));
  }
  return rssStr.join('');
};

//转到某一页
function ToPage(category, page) {
  $("#librarycontent").html(CreatePageContent(category, page));
};

//创建屏幕下部的分页按钮
function GeneratePaginationButtons(category, currentPage, maxPage) {
  var previousPage = currentPage - 1;
  var nextPage = currentPage + 1;
  var strFirst = "";
  var strPrev = "";
  var strNext = "";
  var strLast = "";
  if (previousPage <= 0) {
    previousPage = 1;
  }
  if (nextPage > maxPage) {
    nextPage = maxPage;
  }

  if (currentPage <= 1) {
    clsFirst = 'class="pgdisabled"';
    clsPrev = 'class="pgdisabled"';
    strNext = 'onclick="ToPage(\'' + category + '\',' + nextPage + ')"';
    strLast = 'onclick="ToPage(\'' + category + '\',' + maxPage + ')"';
  } else if (currentPage >= maxPage) {
    clsFirst = 'onclick="ToPage(\'' + category + '\',1)"';
    clsPrev = 'onclick="ToPage(\'' + category + '\',' + previousPage + ')"';
    strNext = 'class="pgdisabled"';
    strLast = 'class="pgdisabled"';
  } else {
    clsFirst = 'onclick="ToPage(\'' + category + '\',1)"';
    clsPrev = 'onclick="ToPage(\'' + category + '\',' + previousPage + ')"';
    strNext = 'onclick="ToPage(\'' + category + '\',' + nextPage + ')"';
    strLast = 'onclick="ToPage(\'' + category + '\',' + maxPage + ')"';
  }
  return '<ul class="paging">' +
    '<li ' + clsFirst + '><<</li>' +
    '<li ' + clsPrev + '>＜</li>' +
    '<li ' + strNext + '>＞</li>' +
    '<li ' + strLast + '>>></li>' +
    '<li class="pageinfo">' + currentPage + '/' + maxPage + '</li></ul>';
};

//选择了某一个分类，根据分类填充内容列表
function SelectCategory(obj, category) {
  if ((category == i18n.catRandom) && g_rssByCat[i18n.catRandom] && g_rssByCat[i18n.catRandom].length > 0) {
    shuffleArray(g_rssByCat[i18n.catRandom]);
  }
  HightlightCategory($(obj).parent());
  ToPage(category, 1);
};

//网友分享库的搜索按钮事件
function DoSearchInShared() {
  var input = $('#search_text');
  var txt = input.val();
  if (txt == "#download") { //下载所有的共享RSS
    DownAllRssToFile();
    input.val("");
    return;
  }

  var $div = $("#all_recipes");
  $div.empty();
  var lang = $("#shared_rss_lang_pick").val();
  BuildSharedRssByCategory(lang, txt);
  CreateCategoryMenu();
  SelectCategory(".category-menu", i18n.catAll); //自动选择第一项
}

//订阅一个共享自定义RSS或Recipe
function SubscribeSharedFeed(title, feedurl, isfulltext, dbId, separated) {
  dbId = dbId || '';
  title = decodeJsSafeStr(title);
  
  $.ajax({
    url: "/customrss/add",
    type: "POST",
    data: {'title': title, 'fulltext': isfulltext, 'url': feedurl, fromsharedlibrary: 'true', 
      'recipeId': dbId, 'separated': separated},
    success: function (resp, textStatus, xhr) {
      if (resp.status == "ok") {
        $('.additional-btns').stop(true).hide();
        $("#toast").fadeIn().delay(3000).fadeOut();
      } else {
        alert(resp.status);
      }
    },
    error: function (xhr, textStatus, errorThrown) {
      alert(textStatus);
    }
  });
}

//用户报告一个共享的自定义RSS源已经失效
function ReportInvalid(title, feedurl, dbId) {
  if (!confirm(i18n.confirmInvalidReport)) {
    return;
  }
  if ((typeof dbId == 'undefined') || !dbId) {
    dbId = '';
  }
  title = decodeJsSafeStr(title);

  $.ajax({
    url: "/library/mgr/reportinvalid",
    type: "POST",
    data: {title: title, url: feedurl, recipeId: dbId},
    success: function (resp, textStatus, xhr) {
      if (resp.status == "ok") {
        ShowSimpleModalDialog('<h2>' + i18n.thanks + '</h2><p>' + i18n.thank4RssFeedback + '</p>');
      } else {
        alert(resp.status);
      }
    },
    error: function (xhr, textStatus, errorThrown) {
      alert(textStatus);
    }
  });
}


//将内容全部下载到本地一个xml文件内
function DownAllRssToFile() {
  if (!g_SharedRss) {
    return;
  }
  var title, url, ftext, cat, rssd, fmtdate, nowdate, lang;
  var elementA = document.createElement('a');
  var aTxt = new Array();
  aTxt.push("<?xml version=\"1.0\" encoding=\"utf-8\" ?>");
  aTxt.push("<opml version=\"2.0\">");
  aTxt.push("<head>");
  aTxt.push("  <title>KindleEar.opml</title>");
  aTxt.push("  <dateCreated>" + new Date() + "</dateCreated>");
  aTxt.push("  <dateModified>" + new Date() + "</dateModified>");
  aTxt.push("  <ownerName>KindleEar</ownerName>");
  aTxt.push("</head>");
  aTxt.push("<body>");
  for (var i = 0; i < g_SharedRss.length; i++) {
    title = escapeXml(g_SharedRss[i].t);
    url = escapeXml(g_SharedRss[i].u);
    cat = escapeXml(g_SharedRss[i].c);
    lang = g_SharedRss[i].l || '';
    ftext = (g_SharedRss[i].f == "false") ? "no" : "yes";
    aTxt.push('  <outline type="rss" text="{0}" title="{0}" xmlUrl="{1}" isFulltext="{2}" category="{3}" language="{4}" />'
      .format(title, url, ftext, cat, lang));
  }
  aTxt.push("</body>");
  aTxt.push("</opml>\n");

  nowdate = new Date();
  fmtdate = "KindleEar_library_" + nowdate.getFullYear() + "_" + ((nowdate.getMonth() + 1)) + "_" + nowdate.getDate() + ".xml";

  elementA.setAttribute("href", "data:text/plain;charset=utf-8," + encodeURIComponent(aTxt.join("\n")));
  elementA.setAttribute("download", fmtdate);
  elementA.style.display = 'none';
  document.body.appendChild(elementA);
  elementA.click();
  document.body.removeChild(elementA);
}

//初始化分享库的几个变量和数组，lastRssTime是服务器最新的
function InitSharedRssData(lastRssTime) {
  if (window.localStorage) { //尝试从本地存储获取数据
    var needLatestTime = false, needData = false;
    var now = getNowSeconds();
    var latestTime = parseInt(window.localStorage.getItem('rss_latest_time'));
    var fetchTime = parseInt(window.localStorage.getItem('rss_fetch_time'));
    var sharedData = window.localStorage.getItem('shared_rss');
    //先使用本机保存的
    try {
      g_SharedRss = JSON.parse(sharedData);
    } catch (e) {console.log(e)}
    SortSharedRssDataArray();
    BuildSharedRssByLang();
    DoSearchInShared();

    //一天内最多只从服务器获取一次分享的RSS列表
    if (!fetchTime || !sharedData || !latestTime) {
      needLatestTime = true;
      needData = true;
    } else if ((now - fetchTime) > 60 * 60 * 24) {
      needLatestTime = true;
    }

    if (needLatestTime) { //向服务器发起请求，要求新的数据
      $.ajax({url: "/library/mgr/latesttime",
        type: "POST",
        async: true, //非阻塞式ajax
        success: function (resp) {
          if (resp.status == "ok") {
            //console.log(resp);
            if (resp.tips) {
              $('#library_tips').html('<div class="notice-box">' + resp.tips + '</div>');
            }
            if (resp.data > latestTime) { //自从上次获取数据以来服务器有数据更新
              FetchDataFromServer();
            }
            window.localStorage.setItem('rss_latest_time', resp.data);
            window.localStorage.setItem('rss_fetch_time', now);
          } else {
            alert(resp.status);
          }
        }
      });
    }

    if (needData) {
      FetchDataFromServer();
    }
  } else { //浏览器不支持本地存储
    $.ajax({url: "/library/mgr/getrss", 
      type: "POST",
      async: true, //非阻塞式ajax
      success: function (resp) {
        if (resp.status == "ok") {
          g_SharedRss = resp.data;
          SortSharedRssDataArray();
          BuildSharedRssByLang();
          DoSearchInShared();
        }
      }
    });
  }
}

//从服务器获取最新的分享数据
function FetchDataFromServer() {
  $.ajax({url: "/library/mgr/getrss", 
    type: "POST",
    async: true, //非阻塞式ajax
    success: function (resp) {
      if (resp.status == "ok") {
        g_SharedRss = resp.data;
        if (g_SharedRss && g_SharedRss.length > 0) {
          window.localStorage.setItem('shared_rss', JSON.stringify(g_SharedRss));
          window.localStorage.setItem('rss_fetch_time', getNowSeconds());
          SortSharedRssDataArray();
          BuildSharedRssByLang();
          DoSearchInShared();
        }
      }
    }
  });
}

$(document).ready(function(){
  InitSharedRssData();
  RegisterHideHambClick();
});
