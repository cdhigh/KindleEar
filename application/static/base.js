//Add a method 'format' to string
//usage: "{0}, {1}".format('tx', 'txt')
String.prototype.format = function() {
  var args = arguments;
  return this.replace(/{(\d+)}/g, function(match, number) {
    return typeof args[number] != 'undefined' ? args[number].toString() : match;
  });
};

//返回当前时间戳，单位为秒
function getNowSeconds() {
  return Math.floor(new Date().getTime() / 1000);
}

//检测浏览器语言
function BrowserLanguage() {
  var lang = "";
  if (navigator.userLanguage) {
    lang = navigator.userLanguage.toLowerCase();  
  } else {
    lang = navigator.language.toLowerCase();  
  }
  if (lang.indexOf('-') != -1) {
    return lang.substring(0, lang.indexOf('-'));
  } else {
    return lang; //.substring(0, 2);
  }
}

//将语种代码翻译为各国语言词汇，使用方法：g_languageNames.of(langCode)
const g_languageNames = new Intl.DisplayNames([BrowserLanguage()], {type: 'language'});

//显示语言名字的便捷函数，如果有的语种代码没有翻译，则返回fallback
function LanguageName(code, fallback) {
  var txt = g_languageNames.of(code);
  return ((txt == code) && fallback) ? fallback : txt;
}

///[start] my.html
var show_menu_box = false;

//注册页面点击事件，任意位置点击隐藏弹出来的ABC圆形按钮
function RegisterHideHambClick() {
  $(document).click(function (e) {
    if (!$(e.target).closest('.hamburger-btn, .additional-btns').length) {
      $('.additional-btns').stop(true).hide();
    }
  });
}

//连接服务器获取内置recipe列表，并按照语言建立一个字典all_builtin_recipes，字典键为语言，值为信息字典列表
function FetchBuiltinRecipesXml() {
  var hasUserLangRss = false;
  var hasEnRss = false;
  //这个是静态文件，flask和浏览器会通过etag来自动使用本地缓存
  $.get('/recipes/builtin_recipes.xml', function(xml) {
    var userLang = BrowserLanguage();
    $(xml).find("recipe").each(function() {
      var title=$(this).attr("title");
      var language=$(this).attr("language").toLowerCase();
      var subs=$(this).attr("needs_subscription");
      subs = ((subs == 'yes') || (subs == 'optional')) ? true : false;
      var description=$(this).attr("description").substring(0, 200);
      var id=$(this).attr("id");

      //忽略各国语言方言，仅取'_'前的部分
      language = language.replace('-', '_');
      var dashIndex = language.indexOf('_');
      if (dashIndex != -1) {
        language = language.substring(0, dashIndex);
      }
      if (language == userLang) {
        hasUserLangRss = true;
      }
      if (language == 'en') {
        hasEnRss = true;
      }

      if (!all_builtin_recipes[language]) {
        all_builtin_recipes[language] = [];
        var $newLangOpt = $('<option value="{0}">{1}</option>'.format(language, LanguageName(language)));
        $("#language_pick").append($newLangOpt);
      }
      all_builtin_recipes[language].push({title: title, description: description, needs_subscription: subs, id: id});
    });
    //自动触发和用户浏览器同样语种的选项
    if (hasUserLangRss) {
      $("#language_pick").find("option[value='{0}']".format(userLang)).attr("selected", true);
      $("#language_pick").val(userLang).trigger('change');
    } else if (hasEnRss) { //如果有英语则选择英语源
      $("#language_pick").find("option[value='en']").attr("selected", true);
      $("#language_pick").val('en').trigger('change');
    } else { //最后只能选择第一个语言
      var firstChild = $("#language_pick").children().first();
      firstChild.attr("selected", true);
      firstChild.trigger('change');
    }
  });
  PopulateLibrary('');
}

//使用符合条件的recipe动态填充网页显示列表
//参数 txt: 如果提供，则标题或描述里面有这个子字符串的才显示，用于搜索
function PopulateLibrary(txt) {
  var $div = $("#all_recipes");
  $div.empty();
  var lang = $("#language_pick").val();
  if (!lang) {
    return;
  }

  //先添加自己上传的recipe
  txt = (txt || '').toLowerCase();
  for (var idx = 0; idx < my_uploaded_recipes.length; idx++) {
    var recipe = my_uploaded_recipes[idx];
    var title = (recipe['title'] || '').toLowerCase();
    var desc = (recipe['description'] || '').toLowerCase();
    if (recipe["language"] == lang) {
      if (!txt || (title.indexOf(txt) != -1) || (desc.indexOf(txt) != -1)) {
        AppendRecipeToLibrary($div, recipe['id']);
      }
    }
  }

  //再添加内置Recipe
  recipes = all_builtin_recipes[lang];
  if (!recipes) {
    return;
  }
  for (var idx = 0; idx < recipes.length; idx++) {
    var recipe = recipes[idx];
    var title = (recipe['title'] || '').toLowerCase();
    var desc = (recipe['description'] || '').toLowerCase();
    if (!txt || (title.indexOf(txt) != -1) || (desc.indexOf(txt) != -1)) {
      AppendRecipeToLibrary($div, recipe['id']);
    }
  }
}

//在Recipe库页面上添加一行信息
function AppendRecipeToLibrary(div, id) {
  var recipe = GetRecipeInfo(id);
  if (Object.keys(recipe).length == 0) {
    return;
  }
  var title = recipe.title;
  var row_str = ['<div class="book box"><div class="titleRow">'];
  row_str.push(title);
  if (id.startsWith("upload:")) {
    row_str.push('<sup> {0}</sup>'.format(i18n.abbrUpl));
  }
  row_str.push('</div><div class="summaryRow">');
  row_str.push(recipe.description);
  row_str.push('</div>');

  hamb_arg = [];
  var fTpl = "{0}('{1}','{2}')";
  if (id.startsWith("upload:")) { //增加汉堡按钮弹出菜单代码
    var id_title = "'{0}','{1}')\"".format(id, title);
    hamb_arg.push({klass: 'btn-A', title: i18n.delete, icon: 'icon-delete', act: fTpl.format('DeleteUploadRecipe', id, title)});
    hamb_arg.push({klass: 'btn-E', title: i18n.share, icon: 'icon-share', act: fTpl.format('StartShareRss', id, title)});
  }
  hamb_arg.push({klass: 'btn-B', title: i18n.viewSrc, icon: 'icon-source', act: "/viewsrc/" + id.replace(':', '__')});
  hamb_arg.push({klass: 'btn-C', title: i18n.subscriSep, icon: 'icon-push', act: fTpl.format('SubscribeRecipe', id, '1')});
  hamb_arg.push({klass: 'btn-D', title: i18n.subscribe, icon: 'icon-subscribe', act: fTpl.format('SubscribeRecipe', id, '0')});
  
  row_str.push(AddHamburgerButton(hamb_arg));
  row_str.push('</div>');
  var new_item = $(row_str.join(''));
  div.append(new_item);
}

//添加汉堡弹出菜单按钮，arg为一个列表，里面的元素为要弹出的菜单项，如果里面有引号的话，需要使用单引号
//[{klass:,title:,icon:,act:,}]
function AddHamburgerButton(arg) {
  var btn_str = [];
  btn_str.push('<button class="hamburger-btn" onclick="ToggleAdditionalBtns(this)">☰</button>');
  btn_str.push('<div class="additional-btns">');
  for (var idx = 0; idx < arg.length; idx++) {
    var item = arg[idx];
    var klass = item.klass;
    var title = item.title;
    var icon = item.icon;
    var act = item.act;
    if (act.startsWith('/') || act.startsWith('http')) { //嵌套一个超链接，打开新窗口
      btn_str.push('<button class="additional-btn {0}" title="{1}"><a href="{2}" target="_blank"><i class="iconfont {3}"></i></a></button>'
      .format(klass, title, act, icon));
    } else {
      btn_str.push('<button class="additional-btn {0}" title="{1}" onclick="{2}"><i class="iconfont {3}"></i></button>'
      .format(klass, title, act, icon));
    }
  }
  btn_str.push('</div>')
  return btn_str.join('');
}

//点击汉堡菜单按钮后显示或隐藏弹出菜单
var additionalBtns;
function ToggleAdditionalBtns(button) {
    if (typeof additionalBtns != 'undefined') {
        additionalBtns.stop(true).hide();
    }
    additionalBtns = $(button).next('.additional-btns');
    additionalBtns.toggle(200);
}

//填充我的自定义RSS订阅区段
function PopulateMyCustomRss() {
  var $div = $('#divMyCustomRss');
  $div.empty();
  for (var idx = 0; idx < my_custom_rss_list.length; idx++) {
    var rss = my_custom_rss_list[idx];
    var title = rss.title;
    var url = rss.url;
    var isfulltext = rss.isfulltext;
    var id = rss['id'];
    var row_str = ['<div class="book box"><div class="titleRow">'];
    row_str.push(title);
    if (isfulltext) {
      row_str.push('<sup> {0}</sup>'.format(i18n.abbrEmb));
    }
    row_str.push('</div><div class="summaryRow"><a target="_blank" href="{0}">'.format(url));
    if (url.length > 100) {
      row_str.push(url.substring(0, 100) + '...');
    } else {
      row_str.push(url);
    }
    row_str.push('</a></div>');

    hamb_arg = [];
    //汉堡按钮弹出菜单代码
    var fTpl = "{0}('{1}','{2}')";
    var fTplAll = "{0}(event,'{1}','{2}','{3}',{4})"; //id,title,url,isfulltext
    hamb_arg.push({klass: 'btn-F', title: i18n.translator, icon: 'icon-translate', act: "/translator/" + id.replace(':', '__')});
    hamb_arg.push({klass: 'btn-G', title: i18n.tts, icon: 'icon-tts', act: "/tts/" + id.replace(':', '__')});
    hamb_arg.push({klass: 'btn-D', title: i18n.share, icon: 'icon-share', act: fTpl.format('StartShareRss', id, title)});
    hamb_arg.push({klass: 'btn-A', title: i18n.deleteCtrlNoConfirm, icon: 'icon-delete', 
      act: fTplAll.format('ShowDeleteCustomRssDialog', id, title, url, isfulltext)});
    row_str.push(AddHamburgerButton(hamb_arg));
    row_str.push('</div>');
    //console.log(row_str.join(''));
    var $new_item = $(row_str.join(''));
    $div.append($new_item);
  }
}

//填充我的Recipe订阅区段
function PopulateMySubscribed() {
  var $div = $('#mysubscribed');
  $div.empty();
  for (var idx = 0; idx < my_booked_recipes.length; idx++) {
    var recipe = my_booked_recipes[idx];
    
    var title = recipe.title;
    var desc = recipe.description;
    var need_subs = recipe.needs_subscription;
    var separated = recipe.separated;
    var recipe_id = recipe.recipe_id;
    var row_str = ['<div class="book box"><div class="titleRow">'];
    row_str.push(title);
    if (recipe_id.startsWith("upload:")) {
      row_str.push('<sup> {0}</sup>'.format(i18n.abbrUpl));
    }
    if (separated) {
      row_str.push('<sup> {0}</sup>'.format(i18n.abbrSep));
    }
    if (need_subs) {
      row_str.push('<sup> {0}</sup>'.format(i18n.abbrLog));
    }
    row_str.push('</div><div class="summaryRow">');
    if (desc.length > 100) {
      row_str.push(desc.substring(0, 100) + '...');
    } else {
      row_str.push(desc);
    }
    row_str.push('</div>');

    hamb_arg = [];
    var fTpl = "{0}('{1}','{2}')";
    //汉堡按钮弹出菜单代码
    if (need_subs) {
        hamb_arg.push({klass: 'btn-C', title: i18n.subscriptionInfo, icon: 'icon-key', act: fTpl.format('AskForSubscriptionInfo', recipe_id, recipe.account)});
    }
    hamb_arg.push({klass: 'btn-F', title: i18n.translator, icon: 'icon-translate', act: "/translator/" + recipe_id.replace(':', '__')});
    hamb_arg.push({klass: 'btn-G', title: i18n.tts, icon: 'icon-tts', act: "/tts/" + recipe_id.replace(':', '__')});
    if (recipe_id.startsWith("upload:")) { //只有自己上传的recipe才能分享，内置的不用分享
      hamb_arg.push({klass: 'btn-D', title: i18n.share, icon: 'icon-share', act: fTpl.format('StartShareRss', recipe_id, title)});
    }
    hamb_arg.push({klass: 'btn-B', title: i18n.viewSrc, icon: 'icon-source', act: "/viewsrc/" + recipe_id.replace(':', '__')});
    hamb_arg.push({klass: 'btn-E', title: i18n.customizeDelivTime, icon: 'icon-schedule', act: fTpl.format('ScheduleRecipe', recipe_id, title)});
    hamb_arg.push({klass: 'btn-A', title: i18n.unsubscribe, icon: 'icon-unsubscribe', act: fTpl.format('UnsubscribeRecipe', recipe_id, title)});
    row_str.push(AddHamburgerButton(hamb_arg));
    row_str.push('</div>');
    //console.log(row_str.join(''));
    var $new_item = $(row_str.join(''));
    $div.append($new_item);
  }
}

//点击了订阅内置或上传的Recipe，发送ajax请求更新服务器信息
function SubscribeRecipe(id, separated) {
  if (typeof separated === 'string') {
    separated = (separated == '1') ? true : false;
  }
  //先判断是否已经订阅
  for (var idx = 0; idx < my_booked_recipes.length; idx++) {
    if (my_booked_recipes[idx]['recipe_id'] == id) {
      alert(i18n.alreadySubscribed);
      return;
    }
  }
  //发post请求
  $.post("/recipe/subscribe", {id: id, separated: separated}, function (data) {
    if (data.status == "ok") {
      var recipe = GetRecipeInfo(id);
      if (Object.keys(recipe).length != 0) {
        var new_item = {recipe_id: id, separated: separated, user: '{{user.name}}', time: (new Date()).getTime(),
        title: recipe.title, description: recipe.description, needs_subscription: recipe.needs_subscription, account: ''};
        my_booked_recipes.unshift(new_item);
        PopulateMySubscribed();
        $('.additional-btns').stop(true).hide();
        $("#toast").fadeIn().delay(2000).fadeOut();
        //订阅后跳转到已订阅区段
        //$("html, body").animate({scrollTop: $("#mysubscribed").offset().top}, {duration:500, easing:"swing"});
      }
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(i18n.cannotSubsRecipe + data.status);
    }
  });
}

//点击了退订内置或上传的Recipe
function UnsubscribeRecipe(id, title) {
  if (!confirm(i18n.areYouSureUnsubscribe.format(title))) {
    return;
  }
  $.post("/recipe/unsubscribe", {id: id}, function (data) {
    if (data.status == "ok") {
      for (var idx = 0; idx < my_booked_recipes.length; idx++) {
        if (my_booked_recipes[idx].recipe_id == id) {
          my_booked_recipes.splice(idx, 1); //删除对应项
          break;
        }
      }
      PopulateMySubscribed();
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(i18n.cannotUnsubsRecipe + data.status);
    }
  });
}

//根据ID找到已订阅recipe的字典
function GetBookedRecipeItem(id) {
  for (var idx = 0; idx < my_booked_recipes.length; idx++) {
    if (my_booked_recipes[idx].recipe_id == id) {
      return my_booked_recipes[idx];
    }
  }
  return '';
}

//设置订阅的Recipe的自定义推送时间
function ScheduleRecipe(id, title) {
  var item = GetBookedRecipeItem(id);
  if (!item) {
    return;
  }
  var days = item.send_days || [];
  var times = item.send_times || [];
  var ostr = ['<h2>' + i18n.customizeDelivTime + '</h2>'];
  ostr.push('<form class="pure-form" action="" method="POST" id="custom_schedule">');
  ostr.push('<input type="text" name="id" value="' + id + '" hidden />');
  ostr.push('<div class="pure-control-group">');
  ostr.push('<p>' + i18n.delivDays + '</p>');
  ostr.push('<div class="schedule_daytimes">')
  ostr.push('<label><input type="checkbox" name="Monday" ' + (days.indexOf(0) > -1 ? 'checked' : '')  + '/>' + i18n.Mon + '</label>');
  ostr.push('<label><input type="checkbox" name="Tuesday" ' + (days.indexOf(1) > -1 ? 'checked' : '')  + '/>' + i18n.Tue + '</label>');
  ostr.push('<label><input type="checkbox" name="Wednesday" ' + (days.indexOf(2) > -1 ? 'checked' : '')  + '/>' + i18n.Wed + '</label>');
  ostr.push('<label><input type="checkbox" name="Thursday" ' + (days.indexOf(3) > -1 ? 'checked' : '')  + '/>' + i18n.Thu + '</label>');
  ostr.push('<label><input type="checkbox" name="Friday" ' + (days.indexOf(4) > -1 ? 'checked' : '')  + '/>' + i18n.Fri + '</label>');
  ostr.push('<label><input type="checkbox" name="Saturday" ' + (days.indexOf(5) > -1 ? 'checked' : '')  + '/>' + i18n.Sat + '</label>');
  ostr.push('<label><input type="checkbox" name="Sunday" ' + (days.indexOf(6) > -1 ? 'checked' : '')  + '/>' + i18n.Sun + '</label>');
  ostr.push('</div></div><div class="pure-control-group">');
  ostr.push('<p>' + i18n.delivTimes + '</p>');
  ostr.push('<div class="schedule_daytimes">')
  for (var t = 0; t < 24; t++) {
    ostr.push('<label><input type="checkbox" name="' + t + '" ' + (times.indexOf(t) > -1 ? 'checked' : '') + '/>' + t.toString().padStart(2, '0') + '</label>');
    if ((t == 7) || (t == 15)) {
      ostr.push('<br/>');
    }
  }
  ostr.push('</div></div></form>');
  showH5Dialog(ostr.join('')).then(function (idx) {
    var formData = $("#custom_schedule").serialize();
    $.ajax({
      url: "/recipe/schedule",
      type: "POST",
      data: formData,
      success: function (resp) {
        if (resp.status == 'ok') {
          item.send_days = resp.send_days;
          item.send_times = resp.send_times;
          ShowSimpleModalDialog('<p>' + i18n.customDelivTimesaved + '</p>');
        } else {
          alert(resp.status);
        }
      },
      error: function (error) {
        alert(error);
      }
    });
  }).catch(function(){});
}

//根据id获取对应recipe的信息，返回一个字典
function GetRecipeInfo(id) {
  if (id.startsWith('builtin:')) {
    for (var lang in all_builtin_recipes) {
      var recipes = all_builtin_recipes[lang];
      for (var i = 0; i < recipes.length; i++) {
        if (recipes[i].id == id) {
          return recipes[i];
        }
      }
    }
  } else {
    for (var idx = 0; idx < my_uploaded_recipes.length; idx++) {
      if (my_uploaded_recipes[idx]['id'] == id) {
        return my_uploaded_recipes[idx];
      }
    }
  }
  return {};
}

//弹出对话框，输入Recipe的登录信息，然后保存到服务器
function AskForSubscriptionInfo(id, account){
  var ostr = ['<h2>' + i18n.subscriptionInfo + '</h2>'];
  ostr.push('<form class="pure-form"><fieldset>');
  ostr.push('<input type="text" id="recipe_account" placeholder="' + i18n.account + '" value="' + account + '" style="margin-left: 10px;" />');
  ostr.push('<input type="password" id="recipe_password" placeholder="' + i18n.password + '" style="margin-left: 10px;" />');
  ostr.push('</fieldset></form>');
  ostr.push('<p>' + i18n.recipeLoginTips + '</p>')
  showH5Dialog(ostr.join('')).then(function (idx) {
    var account = $('#recipe_account');
    var password = $('#recipe_password');
    $.post("/recipelogininfo", {id: id, account: account.val(), password: password.val()},
      function (data) {
        if (data.status == "ok") {
          alert(i18n.congratulations + '\n' + data.result);
        } else if (data.status == i18n.loginRequired) {
          window.location.href = '/login';
        } else {
          alert(i18n.cannotSetSubsInfo + data.status);
        }
      },
    );
  }).catch(function(){});
}

//用户点击了删除自定义RSS按钮，如果按住ctrl键再点击删除，则不需要确认
function ShowDeleteCustomRssDialog(event, rssid, title, url, isfulltext) {
  if (!(event.ctrlKey || event.metaKey)) {
    let msg = i18n.areYouSureDelete.format(title);
    if (!('show' in HTMLDialogElement.prototype)) { //校验兼容性
      if (confirm(msg)) {
        DeleteCustomRss(rssid, title, url, isfulltext, false);
      }
    } else {
      msg += '<p><label><input id="chkReportInvalid" type="checkbox" /> {0}</label>'.format(i18n.reportThisFeedInvalid);
      showH5Dialog(msg).then(function (idx) {
        DeleteCustomRss(rssid, title, url, isfulltext, $('#chkReportInvalid').prop('checked'));
      }).catch(function(){});
    }
  }
}

//删除自定义RSS
function DeleteCustomRss(rssid, title, url, isfulltext, reportInvalid) {
  $.post("/customrss/delete", {id: rssid}, function (data) {
    if (data.status == "ok") {
      for (var idx = 0; idx < my_custom_rss_list.length; idx++) {
        if (my_custom_rss_list[idx].id == rssid) {
          my_custom_rss_list.splice(idx, 1);
          break;
        }
      }
      PopulateMyCustomRss();
      $('#title_to_add').val(title);
      $('#url_to_add').val(url);
      $('#isfulltext').prop('checked', isfulltext);
      if (reportInvalid) { //报告源失效
        console.log('report invalid');
        $.post("/library/mgr/reportinvalid", {title: title, url: url, recipeId: ''});
      }
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(i18n.cannotDelRss + resp.status);
    }
  });
}

//一次性删除所有的自定义RSS
function RemoveAllCustomRss() {
  $.post("/customrss/delete", {id: '#all_custom_rss#'}, function (data) {
    if (data.status == "ok") {
      my_custom_rss_list.length = 0;
      PopulateMyCustomRss();
      $('#title_to_add').val('');
      $('#url_to_add').val('');
      $('#isfulltext').prop('checked', false);
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(resp.status);
    }
  });
  return false;
}

//用户点击了添加自定义RSS按钮
function AddCustomRss() {
  let title_to_add = $('#title_to_add');
  let isfulltext = $('#isfulltext');
  let url_to_add = $('#url_to_add');
  let title = title_to_add.val();
  let url = url_to_add.val();
  if ((title == '#removeall#') && !url) {
    let msg = i18n.areYouSureRemoveAll + '\n' + i18n.areYouSureRemoveAll + '\n' + i18n.areYouSureRemoveAll;
    if (confirm(msg)) {
      return RemoveAllCustomRss();
    } else {
      return false;
    }
  }

  $.post("/customrss/add", {title: title, url: url, fulltext: isfulltext.prop('checked')},
    function (data) {
      if (data.status == "ok") {
        my_custom_rss_list.unshift({title: data.title, url: data.url, 'id': data.id, isfulltext: data.isfulltext});
        PopulateMyCustomRss();
        title_to_add.val("");
        url_to_add.val("");
        isfulltext.prop('checked', false);
      } else if (data.status == i18n.loginRequired) {
        window.location.href = '/login';
      } else {
        alert(i18n.cannotAddRss + data.status);
      }
    },
  );
}

//Global variable
var g_rss_categories = [];

//将一个自定义RSS分享到服务器
function ShareRssToServer(id, title, category, lang) {
  $.post("/library", {id: id, category: category, title: title, lang: lang, creator: window.location.hostname}, function (data) {
    if (data.status == "ok") {
      var idx = g_rss_categories.indexOf(category);
      if (g_rss_categories && (category != "")) {
        if (idx > 0) {
          g_rss_categories.splice(idx, 1); //将刚才使用到的分类移动到开头
        }
        if (idx != 0) {
          g_rss_categories.unshift(category); //添加一个新的类别
        }
      }
      window.localStorage.setItem('rss_category', JSON.stringify(g_rss_categories));
      window.localStorage.setItem('shared_rss', ''); //清除本地存储，让分享库页面从服务器取新数据
      ShowSimpleModalDialog('<p>' + i18n.thankForShare + '</p>');
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(data.status);
    }
  });
}

//显示html5新增的dialog
//content: 对话框html内容
//buttons: 按钮列表，为空则为默认的ok/cancel，否则为[['title', 'class'],]
//last_btn_act: 最后一个按钮的动作，'reject'-调用reject(默认)，'resolve'-调用resolve
//返回一个Promise，then函数的参数为按钮索引，showH5Dialog().then(function (btnIdx){});
function showH5Dialog(content, buttons, last_btn_act) {
  return new Promise(function(resolve, reject) {
    if ((last_btn_act !== 'resolve') && (last_btn_act !== 'reject')) {
      last_btn_act = 'reject';
    }
    if (!buttons) { //默认button，一个ok，一个cancel
      buttons = [[i18n.ok, 'actionButton act h5-dialog-ok'], [i18n.cancel, 'actionButton h5-dialog-cancel']];
    }

    let modal = $('#h5-dialog');
    $('#h5-dialog-content').html(content);

    let btns = $('#h5-dialog-buttons');
    btns.empty();
    buttons.forEach(function(item, idx) {
      let btn = $('<button class="' + item[1] + '">' + item[0] + '</button>');
      if ((idx === buttons.length - 1) && (last_btn_act === 'reject')) {
        btn.on('click', function() {modal[0].close();reject();});
      } else {
        btn.on('click', function() {modal[0].close();resolve(idx);});
      }
      btns.append(btn);
    });

    //点击遮罩层关闭对话框
    modal.on('click', function(event) {
      if (event.target === modal[0]) {
        modal[0].close();
        if (last_btn_act === 'reject') {
          reject();
        } else {
          resolve(buttons.length - 1);
        }
      }
    });
    //右上角的关闭按钮
    $('#h5-dialog-closebutton').on('click', function () {
      modal[0].close();
      if (last_btn_act === 'reject') {
        reject();
      } else {
        resolve(buttons.length - 1);
      }
    });

    // 计算对话框的垂直位置（屏幕中央）
    const windowHeight = $(window).height();
    const dialogHeight = modal.outerHeight();
    const pos = parseInt((windowHeight - dialogHeight) / 3);
    modal.css('top', pos + 'px');
    modal[0].showModal();
  });
}

//显示一个简单的modal对话框，只有一个关闭按钮
function ShowSimpleModalDialog(content) {
  showH5Dialog(content, [[i18n.ok, 'actionButton h5-dialog-cancel']]).then(()=>{}).catch(()=>{});
}

//显示一个分享自定义RSS的对话框
function ShowShareDialog(id, title){
  var all_languages = ['aa','ab','af','ak','sq','am','ar','an','hy','as','av','ae','ay','az','ba','bm','eu','be','bn',
    'bh','bi','bo','bs','br','bg','my','ca','cs','ch','ce','zh','cu','cv','kw','co','cr','cy','cs','da','de','dv','nl',
    'dz','el','en','eo','et','eu','ee','fo','fa','fj','fi','fr','fy','ff','ga','de','gd','ga','gl','gv','el','gn','gu',
    'ht','ha','he','hz','hi','ho','hr','hu','hy','ig','is','io','ii','iu','ie','ia','id','ik','is','it','jv','ja','kl',
    'kn','ks','ka','kr','kk','km','ki','rw','ky','kv','kg','ko','kj','ku','lo','la','lv','li','ln','lt','lb','lu','lg',
    'mk','mh','ml','mi','mr','ms','mi','mk','mg','mt','mn','mi','ms','my','na','nv','nr','nd','ng','ne','nl','nn','nb',
    'no','oc','oj','or','om','os','pa','fa','pi','pl','pt','ps','qu','rm','ro','ro','rn','ru','sg','sa','si','sk','sk',
    'sl','se','sm','sn','sd','so','st','es','sq','sc','sr','ss','su','sw','sv','ty','ta','tt','te','tg','tl','th','bo',
    'ti','to','tn','ts','tk','tr','tw','ug','uk','ur','uz','ve','vi','vo','cy','wa','wo','xh','yi','yo','za','zh','zu'];
  var languages = ['en','fr','zh','es','pt','de','it','ja','ru','tr','ko','ar','cs','nl','el','hi','ms','bn','fa','ur',
    'sw','vi','pa','jv','tl','ha','da','in','no','pl','ro','sv','th'];
  var userLang = BrowserLanguage();
  var ostr = ['<h2>' + i18n.shareLinksHappiness + '</h2>'];
  ostr.push('<div class="pure-g">');
  ostr.push('<div class="pure-u-1 pure-u-md-1-2">');
  ostr.push('<p>' + i18n.category + '</p>');
  ostr.push('<div class="select-editable"><select onchange="this.nextElementSibling.value=this.value;DisplayShareRssLang()"><option value=""></option>');
  for (var idx in g_rss_categories) {
    ostr.push('<option value="{0}">{0}</option>'.format(g_rss_categories[idx]));
  }
  ostr.push('</select><input type="text" name="category" value="" id="txt_share_rss_category" /></div></div>');
  ostr.push('<div class="pure-u-1 pure-u-md-1-2">');
  ostr.push('<p id="sh_rss_lang_disp">{0} ({1})</p>'.format(i18n.language, LanguageName(userLang)));
  ostr.push('<div class="select-editable"><select onchange="this.nextElementSibling.value=this.value;DisplayShareRssLang()"><option value=""></option>');
  for (var idx in languages){
    ostr.push('<option value="{0}">{0}</option>'.format(languages[idx]));
  }
  ostr.push('</select><input type="text" name="category" oninput="DisplayShareRssLang()" value="' + userLang + '" id="txt_share_rss_lang" /></div></div>');
  ostr.push('</div></div>');
  ostr.push('<p>' + i18n.shareCatTips + '</p>');
  showH5Dialog(ostr.join('')).then(function (idx) {
    var category = $("#txt_share_rss_category").val();
    var lang = $("#txt_share_rss_lang").val().toLowerCase();
    if (all_languages.indexOf(lang) != -1) {
      ShareRssToServer(id, title, category, lang);
    } else {
      alert(i18n.langInvalid);
    }
  }).catch(function(){});
}

//在ShowShareDialog()里面的语言文本框有输入语言代码时自动在上面显示可读的语言名称
function DisplayShareRssLang() {
  var code = $('#txt_share_rss_lang').val()
  try {
    $('#sh_rss_lang_disp').text('{0} ({1})'.format(i18n.language, LanguageName(code)));
  } catch(err) {
    $('#sh_rss_lang_disp').text(i18n.language);
  }
}

//点击分享自定义RSS
function StartShareRss(id, title) {
  //从本地存储或服务器获取分类信息
  var now = getNowSeconds();
  var needCat = false;
  var fetchTime = parseInt(window.localStorage.getItem('cat_fetch_time'));
  var catData = window.localStorage.getItem('rss_category');

  //一天内最多只从服务器获取一次分享的RSS列表
  if (!fetchTime || !catData || ((now - fetchTime) > 60 * 60 * 24)) {
    needCat = true;
  }
  if (needCat) {
    $.get("/library/category", function(data) {
      if (data.status == "ok") {
        g_rss_categories = data.categories;
        window.localStorage.setItem('rss_category', JSON.stringify(g_rss_categories));
        window.localStorage.setItem('cat_fetch_time', now);
        ShowShareDialog(id, title);
      } else if (data.status == i18n.loginRequired) {
        window.location.href = '/login';
      } else {
        alert(i18n.cannotAddRss + data.status);
      }
    });
  } else {
    g_rss_categories = JSON.parse(catData);
    ShowShareDialog(id, title);
  }
}

//打开上传Recipe对话框，选择一个文件后上传
function OpenUploadRecipeDialog() {
  var ostr = ['<h2>{0}</h2>'.format(i18n.chooseRecipeFile)];
  ostr.push('<form class="pure-form"><fieldset>');
  ostr.push('<input type="file" id="recipe_file" style="outline:none;"/>');
  ostr.push('</fieldset></form>');
  showH5Dialog(ostr.join('')).then(function (idx) {
    var recipeFile = $('#recipe_file');
    var formData = new FormData();
    var fileData = recipeFile.prop("files")[0];
    if (!fileData) {
      return;
    }
    formData.append("recipe_file", fileData);
    $.ajax({
      url: '/recipe/upload',
      type: 'POST',
      async: false,
      data: formData,
      cache: false,
      contentType: false,
      processData: false,
      success: function (data) {
        if (data.status == "ok") {
          //更新本地数据
          delete data.status;
          let lang = data.language;
          let title = data.title;
          my_uploaded_recipes.unshift(data);
          $("#language_pick").val(lang);
          PopulateLibrary('');
          let msg = `<p>${i18n.recipeUploadedTips}</p>
          <table>
            <tr><td style="text-align:right;padding-right:30px;font-weight:bold;">
            ${i18n.title}</td><td>${title}</td></tr>
            <tr><td style="text-align:right;padding-right:30px;font-weight:bold;">
            ${i18n.language}</td><td>${LanguageName(lang)}</td></tr>
          </table>`;
          ShowSimpleModalDialog(msg);
        } else if (data.status == i18n.loginRequired) {
          window.location.href = '/login';
        } else {
          alert(data.status);
        }
      }
    });
  }).catch(function(){});
}

//删除一个已经上传的Recipe
function DeleteUploadRecipe(id, title) {
  if (!confirm(i18n.areYouSureDelete.format(title))) {
    return;
  }
  $.post("/recipe/delete", {id: id}, function (data) {
    if (data.status == "ok") {
      for (var idx = 0; idx < my_uploaded_recipes.length; idx++) {
        if (my_uploaded_recipes[idx]['id'] == id) {
          my_uploaded_recipes.splice(idx, 1);
          break;
        }
      }
      for (var idx = 0; idx < my_booked_recipes.length; idx++) {
        if (my_booked_recipes[idx].recipe_id == id) {
          my_booked_recipes.splice(idx, 1); //删除对应项
          break;
        }
      }
      PopulateMySubscribed();
      PopulateLibrary('');
      alert(i18n.recipeDeleted);
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(data.status);
    }
  });
}

//在页面下发插入bookmarklet
function insertBookmarkletGmailThis(subscribeUrl, mailPrefix) {
  var parser = $('<a>', {href: subscribeUrl});
  var host = parser.prop('hostname');
  var length = host.length;
  var addr = '';
  if ((length > 12) && host.substr(length - 12, 12) == '.appspot.com') {
    addr = '{0}read@{1}.appspotmail.com'.format(mailPrefix, host.substr(0, length - 12));
  } else {
    addr = '{0}read@{1}'.format(mailPrefix, host);
  }
  
  var parent = $('#bookmarklet_content');
  var newElement = $('<a>', {
    class: 'actionButton',
    href: "javascript:(function(){popw='';Q='';d=document;w=window;if(d.selection){Q=d.selection.createRange().text;}else if(w.getSelection){Q=w.getSelection();}else if(d.getSelection){Q=d.getSelection();}popw=w.open('https://mail.google.com/mail/s?view=cm&fs=1&tf=1&to=" + addr +
        "&su='+encodeURIComponent(d.title)+'&body='+encodeURIComponent(Q)+escape('%5Cn%5Cn')+encodeURIComponent(d.location)+'&zx=RANDOMCRAP&shva=1&disablechatbrowsercheck=1&ui=1','gmailForm','scrollbars=yes,width=550,height=400,top=100,left=75,status=no,resizable=yes');if(!d.all)setTimeout(function(){popw.focus();},50);})();",
    click: function() {
      return false;
    },
    text: i18n.kindleifySelection
  });
  parent.prepend(newElement);
}
///[end] my.html使用的js部分

///[start] adv_delivernow.html使用的部分
//根据选择推送的订阅信息，更新接下来要访问服务器的链接参数，使用get而不使用post是因为gae的cron支持get访问
function UpdateDeliverRecipeLink(name) {
  var recipeIds = [];
  $("input[class='deliver_now_rss_id']").each(function() {
    if ($(this).is(":checked")) {
      recipeIds.push($(this).prop('id').replace(':', "__"));
    }
    var newLink = "/deliver?u=" + name;
    if (recipeIds.length > 0) {
      newLink += "&id=" + recipeIds.join(',');
    }
    $("#deliverNowButton").attr("href", newLink);
  });
}

function SelectDeliverAll() {
  $("input[class='deliver_now_rss_id']").each(function() {
    $(this).prop('checked', true);
  });
};

function SelectDeliverNone() {
  $("input[class='deliver_now_rss_id']").each(function() {
    $(this).prop('checked', false);
  });
};
///[end] adv_delivernow.html

///[start] adv_archive.html
function VerifyInstapaper() {
  var instauser = $("#instapaper_username").val();
  var instapass = $("#instapaper_password").val();

  $.ajax({
    url: "/verifyajax/instapaper",
    type: "POST",
    data: { username: instauser, password: instapass },
    success: function (data, textStatus, jqXHR) {
      if (data.status != "ok") {
        alert("Error:" + data.status);
      } else if (data.correct == 1) {
        ShowSimpleModalDialog('<h2>{0}</h2><p>{1}</p>'.format(i18n.congratulations, i18n.configOk));
      } else {
        alert(i18n.passwordWrong);
      }
    },
    error: function (status) {
      alert(status);
    }
  });
}

//测试wallabag的配置信息是否正确
function VerifyWallaBag() {
  let host = $("#wallabag_host").val();
  let name = $("#wallabag_username").val();
  let passwd = $("#wallabag_password").val();
  let id_ = $("#wallabag_client_id").val();
  let secret = $("#wallabag_client_secret").val();
  let data = {'host': host, 'username': name, 'password': passwd, 'client_id': id_, 
    'client_secret': secret};

  $.ajax({
    url: "/verifyajax/wallabag",
    type: "POST",
    data: data,
    success: function (data, textStatus, jqXHR) {
      if (data.status == "ok") {
        ShowSimpleModalDialog('<h2>{0}</h2><p>{1}</p>'.format(i18n.congratulations, i18n.configOk));
      } else {
        alert(data.status);
      }
    },
    error: function (status) {
      alert(status.toString());
    }
  });
}
///[end] adv_archive.html

///[start] adv_uploadcss.html
var AjaxFileUpload = {
  mimeType: '',
  form: '',
  fileInput: '',
  upButton: '',
  deleteButton: '',
  uploadImage: '',
  url: '',

  filter: function(file) {
    var ret = null;
    if (file) {
      if (file.type.indexOf(this.mimeType) != -1) {
        ret = file;
      } else {
        this.fileInput.val(null);
        alert(i18n.fileIsNotInMime);
      }
    }
    return ret;
  },

  onSelect: function(file) {
    var self = this;
    var html = '';
    if (file) {
      var reader = new FileReader();
      if (self.mimeType.startsWith('image')) {
        reader.onloadend = function() {
          self.preview.attr("src", reader.result);
        }
        reader.readAsDataURL(file);
      } else {
        reader.onloadend = function() {
          self.preview.val(reader.result);
        }
        reader.readAsText(file);
      }
    } else if (self.mimeType.startsWith('image')) {
      self.preview.attr("src", '');
    } else {
      self.preview.val('');
    }
  },

  onProgress: function(loaded, total) {
    var percent = '{0}%'.format(((loaded / total) * 100).toFixed(0));
    this.progress.html(percent).css("display", "inline");
  },

  onSuccess: function(response) {
    response = JSON.parse(response);
    if (response.status == "ok") {
      if (this.progress) {
        this.progress.html("").css("display", "none");
      }
      ShowSimpleModalDialog('<h2>{0}</h2><p>{1}</p>'.format(i18n.congratulations, i18n.fileUploaded));
    } else {
      alert(response.status);
    }
  },

  onFailure: function(status, response) {
    alert(response);
  },

  //获取选择文件，file控件或拖放
  funGetFiles: function(e) {
    var files = e.target.files || e.dataTransfer.files;
    var file = files[0];
    this.file = this.filter(file);
    this.onSelect(this.file);
    return this;
  },

  funUploadFile: function() {
    var self = this;
    var doUpload = function(file) {
      if (file) {
        $.ajax({
          url: self.url,
          type: "POST",
          data: new FormData(self.form[0]),
          processData: false,
          contentType: false,
          xhr: function () {
            var xhr = new window.XMLHttpRequest();
            if (self.progress) {
              xhr.upload.addEventListener("progress", function (e) {
                self.onProgress(e.loaded, e.total);
              }, false);
            }
            return xhr;
          },
          success: function (data, textStatus, xhr) {
            self.onSuccess(xhr.responseText);
          },
          error: function (xhr, textStatus, errorThrown) {
            self.onFailure(xhr.status, xhr.responseText);
          }
        });
      }
    };
    doUpload(self.file);
    return false;
  },

  funDeleteFile: function() {
    var self = this;
    $.ajax({
      url: self.deleteButton.attr('deletehref'),
      type: "POST",
      data: {'action': 'delete'},
      success: function(resp, status, xhr) {
        if (resp.status == "ok") {
          self.fileInput.val(null);
          if (self.mimeType.startsWith('image')) {
            self.preview.attr("src", '');
          } else {
            self.preview.val('');
          }
        } else {
          alert(resp.status);
        }
      },
      error: function(xhr, status, error) {
        alert(status);
      }
    });
  },

  //要实现文件上传功能，外部调用此函数初始化即可
  //mimeType: 接受的文件类型，前缀即可
  //formId: 包含文件选择器和几个功能按钮的form 选择器
  //fileInputId: 文件选择器 选择器
  //upBtnId: 上传确认按钮 选择器
  //delBtnId: 删除按钮 选择器
  //previewTagId: 预览标签 选择器，可以是img或textarea
  //progressId: 可选，一个span，用来显示上传进度
  init: function(mimeType, formId, fileInputId, upBtnId, delBtnId, previewTagId, progressId) {
    var self = this;
    self.mimeType = mimeType;
    self.form = $(formId);
    self.fileInput = $(fileInputId);
    self.upButton = $(upBtnId);
    self.deleteButton = $(delBtnId);
    self.preview = $(previewTagId);
    if (typeof progressId == 'undefined') {
      self.progress = false;
    } else {
      self.progress = $(progressId);
    }
    self.url = self.form.attr('action');
    
    self.fileInput.on("change", function(e) {
      self.funGetFiles(e);
    });
    self.upButton.on("click", function(e) {
      self.funUploadFile(e);
    });
    self.deleteButton.on("click", function(e) {
      self.funDeleteFile(e);
    });
  }
};
///[end] adv_uploadcss.html

///[start] admin.html
//删除一个账号
function DeleteAccount(name) {
  if (!confirm(i18n.areYouSureDelete.format(name))) {
    return;
  }

  $.post("/account/delete", {name: name}, function (data) {
    if (data.status == "ok") {
      ShowSimpleModalDialog('<p>{0}</p>'.format(i18n.accountDeleted));
      window.location.reload(true);
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(data.status);
    }
  });
}
///[end] admin.html

///[start] adv_uploadcover.html
//根据封面的不同属性设置是否可以添加或删除
function InitCoversWidgets() {
  for (var idx = 0; idx < 7; idx++) {
    (function(index) {
      if ($('#img' + index).attr('src').startsWith('/images/')) {
        $('#delImg' + index).hide();
        $('#addUpload' + index).show();
      } else {
        $('#delImg' + index).show();
        $('#addUpload' + index).hide();
        $('#delImg' + index).off().on('click', function() {
          $('#imgFile' + index).val('');
          SetCoverToDefaultImg(index);
        });
      }
    })(idx);
  }
}

//在封面图像上点击加号，弹出选择文件对话框，选择文件后预览并更新全局变量cover_images
//cover_images 为adv_uploadcover.html定义的全局变量
function ChooseCoverImage(idx) {
  $('#imgFile' + idx).click();
  $('#imgFile' + idx).off().on('change', function() {
    var _this = this;
    file = this.files[0];
    if (file) {
      var reader = new FileReader();
      reader.onloadend = function () {
        $('#img' + idx).attr("src", reader.result);
        $('#delImg' + idx).show();
        $('#addUpload' + idx).hide();
        cover_images['cover' + idx] = file;
        $('#delImg' + idx).off().on('click', function() {
          $('#imgFile' + idx).val('');
          SetCoverToDefaultImg(idx);
        });
      };
      reader.readAsDataURL(file);
    } else {
      SetCoverToDefaultImg(idx);
    }
  });
}

//删除一个图像文件后，恢复默认图像
//cover_images 为adv_uploadcover.html定义的全局变量
function SetCoverToDefaultImg(idx) {
  var defaultName = '/images/cover' + idx + '.jpg';
  $('#img' + idx).attr("src", defaultName);
  $('#delImg' + idx).hide();
  $('#addUpload' + idx).show();
  cover_images['cover' + idx] = defaultName;
}

//开始上传图像到服务器
//cover_images 为adv_uploadcover.html定义的全局变量
function startUploadCoversToServer(url) {
  var totalSize = 0;
  var fileDatas = new FormData();
  fileDatas.append('order', $('#coverOrder').val());
  for (var idx = 0; idx < 7; idx++) {
    var coverName = 'cover' + idx;
    var item = cover_images[coverName];
    fileDatas.append(coverName, item);
    if (typeof item == 'object') {
      totalSize += item.size;
    }
  }
  if (totalSize > 16 * 1024 * 1024) { //限制总大小为16M
    alert(i18n.imgSizeToLarge);
    return;
  }

  $("#up_cover_progress").show();
  $.ajax({
      type: "post",
      url: url,
      data: fileDatas,
      cache: false,
      contentType: false,
      processData: false,
      xhr: function() {
        var xhr = new window.XMLHttpRequest();
        xhr.upload.addEventListener("progress", function(evt) {
          if (evt.lengthComputable) {
            var percent = Math.round((evt.loaded / evt.total) * 100);
            $("#up_cover_progress_bar").css("width", "{0}%".format(String(percent)));
            $("#up_cover_progress_bar").html("{0}%".format(String(percent)));
          }
        }, false);
        return xhr;
      },
      success: function(resp, status, xhr) {
        $("#up_cover_progress").hide();
        $("#up_cover_progress_bar").css("width", "0px");
        $("#up_cover_progress_bar").html('');
        if (resp.status == "ok") {
          ShowSimpleModalDialog('<p>{0}</p>'.format(i18n.uploadCoversOk));
        } else {
          alert(resp.status);
        }
      },
      error: function(xhr, status, error) {
        $("#up_cover_progress").hide();
        $("#up_cover_progress_bar").css("width", "0px");
        $("#up_cover_progress_bar").html('');
        alert(status);
      }
  });
}
///[end] adv_uploadcover.html
///[start] book_translator.html
//根据当前可选的翻译引擎列表 g_trans_engines 填充下拉框，currEngineName为Recipe的当前配置
function PopulateTranslatorFields(currEngineName) {
  var engineSel = $('#translator_engine');
  for (var name in g_trans_engines) {
    var selected = (currEngineName == name) ? 'selected="selected"' : '';
    var txt = '<option value="{0}" {1}>{2}</option>'.format(name, selected, g_trans_engines[name].alias);
    engineSel.append($(txt));
  }
  
}

//选择一个翻译引擎后显示或隐藏ApiKey文本框，语种列表也同步更新
//src_lang/dst_lang: 当前recipe的语种代码
function TranslatorEngineFieldChanged(src_lang, dst_lang) {
  //显示或隐藏ApiHost/ApiKey文本框
  var engineName = $('#translator_engine').val();
  var engine = g_trans_engines[engineName];
  if (!engine || engine.need_api_key) {
    $('#api_host_input').attr('placeholder', engine.default_api_host);
    $('#api_keys_textarea').attr('placeholder', engine.api_key_hint);
    $('#api_keys_textarea').prop("required", true);
    $('#translator_api_host').show();
    $('#translator_api_key').show();
  } else {
    $('#api_keys_textarea').prop("required", false);
    $('#translator_api_host').hide();
    $('#translator_api_key').hide();
  }

  //更新语种代码
  var src = $('#translator_src_lang');
  var dst = $('#translator_dst_lang');
  src.empty();
  src.append($('<option value="">Auto detect</option>'));
  dst.empty();
  var source = engine['source'] || {};
  var hasSelected = false;
  for (var name in source) {
    var code = source[name];
    var selected = (code == src_lang) ? 'selected="selected"' : '';
    if (selected) {
      hasSelected = true;
    }
    var txt = '<option value="{0}" {1}>{2}</option>'.format(code, selected, LanguageName(code, name));
    src.append($(txt));
  }
  if (!hasSelected) { //如果没有匹配的语种，选择 "自动"
    src.val("");
  }

  //目标语种
  var target = engine['target'] || {};
  hasSelected = false;
  var enVal = '';
  for (var name in target) {
    var code = target[name];
    var selected = (code == dst_lang) ? 'selected="selected"' : '';
    if (selected) {
      hasSelected = true;
    }
    if ((code == 'EN') || (code == 'en')) { //有的是大写，有的是小写
      enVal = code;
    }
    var txt = '<option value="{0}" {1}>{2}</option>'.format(code, selected, LanguageName(code, name));
    dst.append($(txt));
  }
  if (!hasSelected) { //如果没有匹配的语种，默认选择英语
    dst.val(enVal);
  }
}

//测试Recipe的翻译器设置是否正确
function TestTranslator(recipeId) {
  var text = $('#translator_test_src_text').val();
  //console.log(text);
  var divDst = $('#translator_test_dst_text');
  divDst.val(i18n.translating);
  recipeId = recipeId.replace(':', '__');
  $.post("/translator/test/" + recipeId, {recipeId: recipeId, text: text}, function (data) {
    if (data.status == "ok") {
      divDst.val(data.text);
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      divDst.val('');
      alert(data.status);
    }
  });
}
///[end] book_translator.html

///[start] book_audiolator.html
//根据当前可选的TTS引擎列表 g_tts_engines 填充下拉框，currEngineName为Recipe的当前配置
function PopulateTTSFields(currEngineName) {
  var engineSel = $('#tts_engine');
  for (var name in g_tts_engines) {
    var selected = (currEngineName == name) ? 'selected="selected"' : '';
    var txt = '<option value="{0}" {1}>{2}</option>'.format(name, selected, g_tts_engines[name].alias);
    engineSel.append($(txt));
  }
}

//选择一个TTS引擎后显示或隐藏各种文本框
//language: 当前recipe的TTS语种代码
//region: 当前recipe的region代码
function TTSEngineFieldChanged(language, region) {
  var engineName = $('#tts_engine').val();
  var engine = g_tts_engines[engineName];
  if (engine.need_api_key) { //设置apikey是否可见
    $('#tts_api_key_input').attr('placeholder', engine.api_key_hint);
    $('#tts_api_key_input').prop("required", true);
    $('#tts_api_key').show();
  } else {
    $('#tts_api_key_input').prop("required", false);
    $('#tts_api_key').hide();
  }
  let hasSelected = false;
  if (engine.regions && Object.keys(engine.regions).length > 0) { //填充region
    $('#tts_region_div').show();
    let region_sel = $('#tts_region_sel');
    for (const [code, name] of Object.entries(engine.regions)) {
      let selected = (code == region) ? 'selected="selected"' : '';
      if (selected) {
        hasSelected = true;
      }
      let txt = '<option value="{0}" {1}>{2}</option>'.format(code, selected, name + ' (' + code + ')');
      region_sel.append($(txt));
    }
  } else {
    $('#tts_region_div').hide();
  }
  
  //设置提示的链接
  let region_a = $('#tts_region_a');
  if (engine.region_url) {
    region_a.attr('href', engine.region_url);
    region_a.removeAttr('onclick');
    region_a.css('text-decoration', 'underline dotted');
  } else {
    region_a.attr('href', 'javascript:void(0)');
    region_a.attr('onclick', 'return false;');
    region_a.css('text-decoration', 'none');
  }
  let voice_a = $('#tts_voice_a');
  if (engine.voice_url) {
    voice_a.attr('href', engine.voice_url);
    voice_a.removeAttr('onclick');
    voice_a.css('text-decoration', 'underline dotted');
  } else {
    voice_a.attr('href', 'javascript:void(0)');
    voice_a.attr('onclick', 'return false;');
    voice_a.css('text-decoration', 'none');
  }
  
  //更新语种代码
  let tts_language_sel = $('#tts_language_sel');
  let languages = engine.languages || {}; //键为语种代码，值为语音名字列表
  tts_language_sel.empty();
  let enName = 'en';
  hasSelected = false;
  for (const code of Object.keys(languages)) {
    let selected = (code == language) ? 'selected="selected"' : '';
    if (selected) {
      hasSelected = true;
    } else if (code.startsWith('en')) {
      enName = code;
    }
    let txt = '<option value="{0}" {1}>{2}</option>'.format(code, selected, LanguageName(code, code));
    tts_language_sel.append($(txt));
  }
  if (!hasSelected) { //如果没有匹配的语种，选择英语
    tts_language_sel.val(enName);
  }
}

//选择一个TTS语种后填充可选的语音列表
//currVoice: 当前recipe的TTS语音名字
function TTSLanguageFieldChanged(currVoice) {
  var engineName = $('#tts_engine').val();
  var engine = g_tts_engines[engineName]; //当前选择的TTS引擎
  let code = $('#tts_language_sel').val(); //当前选择的语种代码
  let voice_sel = $('#tts_voice_sel');
  voice_sel.empty();
  if (!engine || !code) {
    return;
  }
  let languages = engine.languages || {}; //键为语种代码，值为语音名字列表
  let voices = languages[code];
  if (!voices || voices.length == 0) {
    $('#tts_voice_div').hide();
    voice_sel.val('');
  } else {
    $('#tts_voice_div').show();
    let hasSelected = false;
    for (const voice of voices) {
      let selected = (voice == currVoice) ? 'selected="selected"' : '';
      if (selected) {
        hasSelected = true;
      }
      let txt = '<option value="{0}" {1}>{0}</option>'.format(voice, selected);
      voice_sel.append($(txt));
    }
    if (!hasSelected) { //如果没有匹配的语种，选择第一个
      voice_sel.val(voices[0] || '');
    }
  }
}

//一个base64字符串转换为一个blob对象
function b64toBlob(data, type) {    
    var byteString = atob(data);
    var ab = new ArrayBuffer(byteString.length);
    var ia = new Uint8Array(ab);
    for (var i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: type });
}

//测试TTS设置
function TestTTS(recipeId) {
  var text = $('#tts_test_src_text').val();
  var ttsAudio = $('#tts_audio_player');
  recipeId = recipeId.replace(':', '__');
  $.post("/tts/test/" + recipeId, {recipeId: recipeId, text: text}, function (data) {
    if (data.status == "ok") {
      let blob = b64toBlob(data.audio, data.mime);
      let audioUrl = ttsAudio.attr('src');
      if (audioUrl) {
        try {
          URL.revokeObjectURL(audioUrl);
        } catch (e) {}
      }
      audioUrl = URL.createObjectURL(blob);
      ttsAudio.attr('src', audioUrl);
      ttsAudio[0].play();
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(data.status);
    }
  });
}
///[end] book_audiolator.html