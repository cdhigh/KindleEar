//Add a method 'format' to string
//usage: "{0}, {1}".format('tx', 'txt')
String.prototype.format = function() {
  var args = arguments;
  return this.replace(/{(\d+)}/g, function(match, number) {
    return typeof args[number] != 'undefined' ? args[number] : match;
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
    return lang.substring(0, 2);
  }
}
//将语种代码翻译为各国语言词汇，使用方法：g_languageNames.of(langCode)
const g_languageNames = new Intl.DisplayNames([BrowserLanguage()], {type: 'language'});

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
      var needs_subscription=$(this).attr("needs_subscription");
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
        var $newLangOpt = $('<option value="' + language +'">' + g_languageNames.of(language) + '</option>');
        $("#language_pick").append($newLangOpt);
      }
      all_builtin_recipes[language].push({title: title, description: description, needs_subscription: needs_subscription, id: id});
    });
    //自动触发和用户浏览器同样语种的选项
    if (hasUserLangRss) {
      $("#language_pick").find("option[value='" + userLang + "']").attr("selected", true);
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
  for (var idx = 0; idx < my_uploaded_recipes.length; idx++) {
    var recipe = my_uploaded_recipes[idx];
    var title = recipe['title'];
    var desc = recipe['description'];
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
    var title = recipe['title'];
    var desc = recipe['description'];
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
  if (id.startsWith("upload:")) {
    row_str.push('<i class="iconfont icon-upload icon-as-tag"></i>' + title);
  } else {
    row_str.push(title);
  }
  row_str.push('</div><div class="summaryRow">');
  row_str.push(recipe.description);
  row_str.push('</div>');

  hamb_arg = [];
  if (id.startsWith("upload:")) { //增加汉堡按钮弹出菜单代码
    var id_title = id + "','" + title + "')\"";
    hamb_arg.push({klass: 'btn-A', title: i18n.delete, icon: 'icon-delete', act: "DeleteUploadRecipe('" + id + "','" + title + "')"});
    hamb_arg.push({klass: 'btn-E', title: i18n.share, icon: 'icon-share', act: "StartShareRss('" + id_title});
  }
  hamb_arg.push({klass: 'btn-B', title: i18n.viewSrc, icon: 'icon-source', act: "/viewsrc/" + id.replace(':', '__')});
  hamb_arg.push({klass: 'btn-C', title: i18n.subscriSep, icon: 'icon-push', act: "SubscribeRecipe('" + id + "',1)"});
  hamb_arg.push({klass: 'btn-D', title: i18n.subscribe, icon: 'icon-subscribe', act: "SubscribeRecipe('" + id + "',0)"});
  
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
    btn_str.push('<button class="additional-btn ');
    btn_str.push(klass);
    btn_str.push('" title="');
    btn_str.push(title + '"');
    if (act.startsWith('/') || act.startsWith('http')) { //嵌套一个超链接，打开新窗口
      btn_str.push('><a href="' + act + '" target="_blank"><i class="iconfont ');
      btn_str.push(icon + '"></i></a>');
    } else {
      btn_str.push(' onclick="');
      btn_str.push(act);
      btn_str.push('"><i class="iconfont ' + icon + '"></i>');
    }
    btn_str.push('</button>');
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
      row_str.push('<sup> Emb</sup>');
    }
    row_str.push('</div><div class="summaryRow">');
    if (url.length > 100) {
      row_str.push(url.substring(0, 100) + '...');
    } else {
      row_str.push(url);
    }
    row_str.push('</div>');

    hamb_arg = [];
    //汉堡按钮弹出菜单代码
    var id_title_str = id + "','" + title + "')\"";
    hamb_arg.push({klass: 'btn-D', title: i18n.share, icon: 'icon-share', act: "StartShareRss('" + id_title_str});
    hamb_arg.push({klass: 'btn-A', title: i18n.delete, icon: 'icon-delete', act: "DeleteCustomRss('" + id_title_str});
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
    if (recipe_id.startsWith("upload:")) {
      row_str.push('<i class="iconfont icon-upload icon-as-tag"></i>' + title);
    } else {
      row_str.push(title);
    }
    if (separated) {
      //row_str.push('<img alt="' + i18n.separated + '" src="static/separate.gif" border="0" />');
      row_str.push('<sup> Sep</sup>');
    }
    row_str.push('</div><div class="summaryRow">');
    if (desc.length > 100) {
      row_str.push(desc.substring(0, 100) + '...');
    } else {
      row_str.push(desc);
    }
    row_str.push('</div>');

    hamb_arg = [];
    var id_title = recipe_id + "','" + title + "')\"";
    //汉堡按钮弹出菜单代码
    if (need_subs && need_subs != 'no' && need_subs != 'false' && need_subs != 0) {
        hamb_arg.push({klass: 'btn-C', title: i18n.subscriptionInfo, icon: 'icon-key', act: "AskForSubscriptionInfo('" + recipe_id + "', '" + recipe.account + "')"});
    }
    if (recipe_id.startsWith("upload:")) { //只有自己上传的recipe才能分享，内置的不用分享
      hamb_arg.push({klass: 'btn-D', title: i18n.share, icon: 'icon-share', act: "StartShareRss('" + id_title});
    }
    hamb_arg.push({klass: 'btn-B', title: i18n.viewSrc, icon: 'icon-source', act: "/viewsrc/" + recipe_id.replace(':', '__')});
    hamb_arg.push({klass: 'btn-E', title: i18n.customizeDelivTime, icon: 'icon-schedule', act: "ScheduleRecipe('" + id_title});
    hamb_arg.push({klass: 'btn-A', title: i18n.unsubscribe, icon: 'icon-unsubscribe', act: "UnsubscribeRecipe('" + id_title});
    row_str.push(AddHamburgerButton(hamb_arg));
    row_str.push('</div>');
    //console.log(row_str.join(''));
    var $new_item = $(row_str.join(''));
    $div.append($new_item);
  }
}

//点击了订阅内置或上传的Recipe，发送ajax请求更新服务器信息
function SubscribeRecipe(id, separated) {
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
  var modal = new tingle.modal({footer: true});
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
  modal.setContent(ostr.join(''));
  modal.addFooterBtn(i18n.cancel, 'actionButton', function() {
    modal.close();
  });
  modal.addFooterBtn(i18n.submit, 'actionButton act', function() {
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
        modal.close();
      },
      error: function (error) {
        alert(error);
        modal.close();
      }
    });
  });
  modal.open();
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
  var modal = new tingle.modal({footer:true});
  var ostr = ['<h2>' + i18n.subscriptionInfo + '</h2>'];
  ostr.push('<form class="pure-form"><fieldset>');
  ostr.push('<input type="text" id="recipe_account" placeholder="' + i18n.account + '" value="' + account + '" style="margin-left: 10px;" />');
  ostr.push('<input type="password" id="recipe_password" placeholder="' + i18n.password + '" style="margin-left: 10px;" />');
  ostr.push('</fieldset></form>');
  ostr.push('<p>' + i18n.recipeLoginTips + '</p>')

  modal.setContent(ostr.join(''));
  modal.addFooterBtn(i18n.cancel, 'actionButton', function() {
    modal.close();
  });
  modal.addFooterBtn(i18n.submit, 'actionButton act', function() {
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
        modal.close();
      },
    );
  });
  modal.open();
}

//用户点击了删除自定义RSS按钮
function DeleteCustomRss(rssid, title) {
  if (!confirm(i18n.areYouSureDelete.format(title))) {
    return;
  }
  
  $.post("/customrss/delete", {id: rssid}, function (data) {
    if (data.status == "ok") {
      for (var idx = 0; idx < my_custom_rss_list.length; idx++) {
        if (my_custom_rss_list[idx].id == rssid) {
          my_custom_rss_list.splice(idx, 1);
          break;
        }
      }
      PopulateMyCustomRss();
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(i18n.cannotDelRss + resp.status);
    }
  });
}

//用户点击了添加自定义RSS按钮
function AddCustomRss() {
  var title_to_add = $('#title_to_add');
  var isfulltext = $('#isfulltext');
  var url_to_add = $('#url_to_add');
  $.post("/customrss/add", {title: title_to_add.val(), fulltext: isfulltext.prop('checked'), url: url_to_add.val()},
    function (data) {
      if (data.status == "ok") {
        my_custom_rss_list.unshift({title: data.title, url: data.url, 'id': data.id, isfulltext: data.isfulltext});
        PopulateMyCustomRss();
        title_to_add.val("");
        url_to_add.val("");
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
      if (g_rss_categories && (category != "")) { //将刚才使用到的分类移动到开头
        if (idx > 0){
          g_rss_categories.splice(idx, 1);
        }
        if (idx != 0) {
          g_rss_categories.unshift(category);
        }
      }
      window.localStorage.setItem('rss_category', JSON.stringify(g_rss_categories));
      window.localStorage.setItem('shared_rss', ''); //让分享库页面从服务器取新数据
      ShowSimpleModalDialog('<p>' + i18n.thankForShare + '</p>');
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(data.status);
    }
  });
}

//显示一个简单的modal对话框，只有一个关闭按钮
function ShowSimpleModalDialog(content) {
  var modal = new tingle.modal({footer: true});
  modal.setContent(content);
  modal.addFooterBtn(i18n.close, 'actionButton', function() {
    modal.close();
  });
  modal.open();
}

//显示一个分享自定义RSS的对话框
function ShowShareDialog(id, title){
  var all_languages = ['aa','ab','af','ak','sq','am','ar','an','hy','as','av','ae','ay','az','ba','bm','eu','be','bn','bh','bi','bo','bs','br','bg','my','ca','cs','ch','ce','zh','cu','cv','kw','co','cr','cy','cs','da','de','dv','nl','dz','el','en','eo','et','eu','ee','fo','fa','fj','fi','fr','fy','ff','ga','de','gd','ga','gl','gv','el','gn','gu','ht','ha','he','hz','hi','ho','hr','hu','hy','ig','is','io','ii','iu','ie','ia','id','ik','is','it','jv','ja','kl','kn','ks','ka','kr','kk','km','ki','rw','ky','kv','kg','ko','kj','ku','lo','la','lv','li','ln','lt','lb','lu','lg','mk','mh','ml','mi','mr','ms','mi','mk','mg','mt','mn','mi','ms','my','na','nv','nr','nd','ng','ne','nl','nn','nb','no','oc','oj','or','om','os','pa','fa','pi','pl','pt','ps','qu','rm','ro','ro','rn','ru','sg','sa','si','sk','sk','sl','se','sm','sn','sd','so','st','es','sq','sc','sr','ss','su','sw','sv','ty','ta','tt','te','tg','tl','th','bo','ti','to','tn','ts','tk','tr','tw','ug','uk','ur','uz','ve','vi','vo','cy','wa','wo','xh','yi','yo','za','zh','zu'];
  var languages = ['en','fr','zh','es','pt','de','it','ja','ru','tr','ko','ar','cs','nl','el','hi','ms','bn','fa','ur','sw','vi','pa','jv','tl','ha'];
  var userLang = BrowserLanguage();
  var modal = new tingle.modal({footer: true});
  var ostr = ['<h2>' + i18n.shareLinksHappiness + '</h2>'];
  ostr.push('<div class="pure-g">');
  ostr.push('<div class="pure-u-1 pure-u-md-1-2">');
  ostr.push('<p>' + i18n.category + '</p>');
  ostr.push('<div class="select-editable"><select onchange="this.nextElementSibling.value=this.value;DisplayShareRssLang()"><option value=""></option>');
  for (var idx in g_rss_categories){
    ostr.push('<option value="' + g_rss_categories[idx] + '">' + g_rss_categories[idx] + '</option>');
  }
  ostr.push('</select><input type="text" name="category" value="" id="txt_share_rss_category" /></div></div>');
  ostr.push('<div class="pure-u-1 pure-u-md-1-2">');
  ostr.push('<p id="sh_rss_lang_disp">' + i18n.language + ' (' + g_languageNames.of(userLang) + ')</p>');
  ostr.push('<div class="select-editable"><select onchange="this.nextElementSibling.value=this.value;DisplayShareRssLang()"><option value=""></option>');
  for (var idx in languages){
    ostr.push('<option value="' + languages[idx] + '">' + languages[idx] + '</option>');
  }
  ostr.push('</select><input type="text" name="category" oninput="DisplayShareRssLang()" value="' + userLang + '" id="txt_share_rss_lang" /></div></div>');
  ostr.push('</div></div>');
  ostr.push('<p>' + i18n.shareCatTips + '</p>');
  
  modal.setContent(ostr.join(''));
  modal.addFooterBtn(i18n.cancel, 'actionButton', function() {
    modal.close();
  });
  modal.addFooterBtn(i18n.share, 'actionButton act', function() {
    var category = $("#txt_share_rss_category").val();
    var lang = $("#txt_share_rss_lang").val().toLowerCase();
    if (all_languages.indexOf(lang) != -1) {
      ShareRssToServer(id, title, category, lang);
      modal.close();
    } else {
      alert(i18n.langInvalid);
    }
  });
  modal.open();
}

//在ShowShareDialog()里面的语言文本框有输入语言代码时自动在上面显示可读的语言名称
function DisplayShareRssLang() {
  try {
    $('#sh_rss_lang_disp').text(i18n.language + ' (' + g_languageNames.of($('#txt_share_rss_lang').val()) + ')');
  } catch(err) {
    $('#sh_rss_lang_disp').text(i18n.language);
  }
}

//点击分享自定义RSS
function StartShareRss(id, title) {
  //从本地存储或服务器获取分类信息
  if (!g_rss_categories) {
    var now = getNowSeconds();
    var needCat = false;
    var fetchTime = parseInt(window.localStorage.getItem('cat_fetch_time'));
    var catData = window.localStorage.getItem('rss_category');

    //一天内最多只从服务器获取一次分享的RSS列表
    if (!fetchTime || !catData || ((fetchTime - now) > 60 * 60 * 24)) {
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
  } else {
    ShowShareDialog(id, title);
  }
}

//打开上传Recipe对话框，选择一个文件后上传
function OpenUploadRecipeDialog() {
  var modal = new tingle.modal({footer:true});
  var ostr = ['<h2>' + i18n.chooseRecipeFile + '</h2>'];
  ostr.push('<form class="pure-form"><fieldset>');
  ostr.push('<input type="file" id="recipe_file" />');
  ostr.push('</fieldset></form>');
  modal.setContent(ostr.join(''));
  modal.addFooterBtn(i18n.cancel, 'actionButton', function() {
    modal.close();
  });
  modal.addFooterBtn(i18n.submit, 'actionButton act', function() {
    var recipeFile = $('#recipe_file');
    var formData = new FormData();
    var fileData = recipeFile.prop("files")[0];
    if (!fileData) {
      modal.close();
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
          modal.close();
          //更新本地数据
          delete data.status;
          my_uploaded_recipes.unshift(data);
          PopulateLibrary();
          ShowSimpleModalDialog('<h2>' + i18n.congratulations + '</h2><p>' + i18n.recipeUploadedTips + '</p>');
        } else if (data.status == i18n.loginRequired) {
          window.location.href = '/login';
        } else {
          alert(data.status);
        }
      }
    });
  });
  modal.open();
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
      PopulateLibrary();
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
  var parser = $('<a>', {
    href: subscribeUrl
  });
  var host = parser.prop('hostname');
  var length = host.length;
  var addr = '';
  if ((length > 12) && host.substr(length - 12, 12) == '.appspot.com') {
    addr = mailPrefix + 'read@' + host.substr(0, length - 12) + '.appspotmail.com';
  } else {
    return;
  }
  
  var parent = $('#bookmarklet_content');
  var newElement = $('<a>', {
    class: 'actionButton',
    href: "javascript:(function(){popw='';Q='';d=document;w=window;if(d.selection){Q=d.selection.createRange().text;}else if(w.getSelection){Q=w.getSelection();}else if(d.getSelection){Q=d.getSelection();}popw=w.open('http://mail.google.com/mail/s?view=cm&fs=1&tf=1&to=" + mailUrl +
        "&su='+encodeURIComponent(d.title)+'&body='+encodeURIComponent(Q)+escape('%5Cn%5Cn')+encodeURIComponent(d.location)+'&zx=RANDOMCRAP&shva=1&disablechatbrowsercheck=1&ui=1','gmailForm','scrollbars=yes,width=550,height=400,top=100,left=75,status=no,resizable=yes');if(!d.all)setTimeout(function(){popw.focus();},50);})();",
    click: function() {
      return false;
    },
    text: i18n.readWithKindle
  });
  parent.prepend(newElement);
}
///[end] my.html使用的js部分

///[start] advdelivernow.html使用的部分
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
///[end] advdelivernow.html

///[start] advarchive.html
function verifyInstapaper() {
  var notifyInstapaperVerify = function () {
    $("#averInstapaper").html(i18n.verify);
  };
  var instauser = $("#instapaper_username").val();
  var instapass = $("#instapaper_password").val();

  notifyInstapaperVerify();

  $.ajax({
    url: "/verifyajax/instapaper",
    type: "POST",
    data: { username: instauser, password: instapass },
    success: function (data, textStatus, jqXHR) {
      if (data.status != "ok") {
        alert("Error:" + data.status);
        notifyInstapaperVerify();
      } else if (data.correct == 1) {
        alert(i18n.congratulations);
        $("#averInstapaper").html(i18n.verified);
      } else {
        alert(i18n.passwordWrong);
        notifyInstapaperVerify();
      }
    },
    error: function (status) {
      alert(status);
      notifyInstapaperVerify();
    }
  });
}
///[end] advarchive.html

///[start] advuploadcss.html
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
    var percent = ((loaded / total) * 100).toFixed(0) + '%';
    this.progress.html(percent).css("display", "inline");
  },

  onSuccess: function(response) {
    response = JSON.parse(response);
    if (response.status == "ok") {
      if (this.progress) {
        this.progress.html("").css("display", "none");
      }
      ShowSimpleModalDialog('<h2>' + i18n.congratulations + '</h2><p>' + i18n.fileUploaded + '</p>');
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
///[end] advuploadcss.html

///[start] admin.html
//添加一个账号
function AddAccount(name) {
  var newName = $('#new_username').val();
  var newPwd1 = $('#new_u_pwd1').val();
  var newPwd2 = $('#new_u_pwd2').val();
  var expiration = $('#new_u_expiration').val();
  if (!newName || !newPwd1 || !newPwd2) {
    alert(i18n.namePwdEmpty);
    return;
  } else if (newPwd1 != newPwd2) {
    alert(i18n.pwdDismatch);
    return;
  }

  $.post("/admin", {actType: 'add', new_username: newName, new_u_pwd1: newPwd1, new_u_pwd2: newPwd2, 
    new_u_expiration: expiration}, function (data) {
    if (data.status == "ok") {
      $('#new_username').val('');
      $('#new_u_pwd1').val('');
      $('#new_u_pwd2').val('');
      ShowSimpleModalDialog('<p>' + i18n.addAccountOk + '</p>');
      window.location.reload(true);
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(data.status);
    }
  });
}

//修改账号的密码
function ChangeAccountPassword(name) {
  var oldPwd = $('#orgpwd').val();
  var newPwd1 = $('#newpwd1').val();
  var newPwd2 = $('#newpwd2').val();
  if (!oldPwd || !newPwd1 || !newPwd2) {
    alert(i18n.namePwdEmpty);
    return;
  } else if (newPwd1 != newPwd2) {
    alert(i18n.pwdDismatch);
    return;
  }

  $.post("/admin", {actType: 'change', name: name, op: oldPwd, p1: newPwd1, p2: newPwd2}, function (data) {
    if (data.status == "ok") {
      $('#orgpwd').val('');
      $('#newpwd1').val('');
      $('#newpwd2').val('');
      ShowSimpleModalDialog('<p>' + i18n.chPwdSuccess + '</p>');
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(data.status);
    }
  });
}

//删除一个账号
function DeleteAccount(name) {
  if (!confirm(i18n.areYouSureDelete.format(name))) {
    return;
  }

  $.post("/admin", {actType: 'delete', name: name}, function (data) {
    if (data.status == "ok") {
      ShowSimpleModalDialog('<p>' + i18n.accountDeleted + '</p>');
      window.location.reload(true);
    } else if (data.status == i18n.loginRequired) {
      window.location.href = '/login';
    } else {
      alert(data.status);
    }
  });
}
///[end] admin.html

///[start] advcoverimage.html
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
//cover_images 为advcoverimage.html定义的全局变量
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
//cover_images 为advcoverimage.html定义的全局变量
function SetCoverToDefaultImg(idx) {
  var defaultName = '/images/cover' + idx + '.jpg';
  $('#img' + idx).attr("src", defaultName);
  $('#delImg' + idx).hide();
  $('#addUpload' + idx).show();
  cover_images['cover' + idx] = defaultName;
}

//开始上传图像到服务器
//cover_images 为advcoverimage.html定义的全局变量
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
  
  $.ajax({
      type: "post",
      url: url,
      data: fileDatas,
      cache: false,
      contentType: false,
      processData: false,
      success: function(resp, status, xhr) {
        if (resp.status == "ok") {
          ShowSimpleModalDialog('<p>' + i18n.uploadCoversOk + '</p>');
        } else {
          alert(resp.status);
        }
      },
      error: function(xhr, status, error) {
        alert(status);
      }
  });
}
///[end] advcoverimage.html
