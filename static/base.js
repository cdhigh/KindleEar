
///[start] my.html使用的js部分
//连接服务器获取内置recipe列表，并按照语言建立一个字典，字典键为语言，值为信息字典列表
var all_builtin_recipes = {};
var show_menu_box = false;

//注册页面点击事件，任意位置点击隐藏弹出来的ABC圆形按钮
function RegisterHideHambClick() {
  $(document).click(function (e) {
    if (!$(e.target).closest('.hamburger-btn, .additional-btns').length) {
      $('.additional-btns').stop(true).hide();
    }
  });
}

//连接服务器获取内置的Recipe列表
function FetchBuiltinRecipesXml() {
  $.get('/builtin_recipes.xml?x=1',function(xml) {
    var user_lang = BrowserLanguage();
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
      const languageNames = new Intl.DisplayNames([user_lang], {type: 'language'}); //将语种代码翻译为各国语言词汇

      if (!all_builtin_recipes[language]) {
        all_builtin_recipes[language] = [];
        var $new_language = $('<option value="' + language +'">' + languageNames.of(language) + '</option>');
        $("#language_pick").append($new_language);
      }
      all_builtin_recipes[language].push({title: title, description: description, needs_subscription: needs_subscription, id: id});
    });
    //自动触发和用户浏览器同样语种的选项
    $("#language_pick").find("option[value='" + user_lang + "']").attr("selected", true);
    $("#language_pick").val(user_lang).trigger('change');
  });
  PopulateLibrary('');
}

//在界面上选择了一项Recipe语种，将对应语种的recipe显示出来
$("#language_pick").on("change", function(){
  PopulateLibrary('');
});

//在指定语言里面搜索标题或描述
$("#search_recipe").on("keyup", function() {
  PopulateLibrary($(this).val());
});

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
  if (id.startsWith("uploaded:")) {
    row_str.push('<i class="iconfont icon-upload icon-as-tag"></i>' + title);
  } else {
    row_str.push(title);
  }
  row_str.push('</div><div class="summaryRow">');
  row_str.push(recipe.description);
  row_str.push('</div>');

  hamb_arg = [];
  if (id.startsWith("uploaded:")) { //增加汉堡按钮弹出菜单代码
    hamb_arg.push({klass: 'btn-A', title: i18n.delete, icon: 'icon-delete', act: "DeleteUploadRecipe('" + id + "','" + title + "')"});
  }
  hamb_arg.push({klass: 'btn-B', title: i18n.viewSrc, icon: 'icon-sourcecode', act: "/viewsrc/" + id.replace(':', '__')});
  hamb_arg.push({klass: 'btn-C', title: i18n.subscriSep, icon: 'icon-push', act: "SubscribeRecipe('" + id + "',1)"});
  hamb_arg.push({klass: 'btn-D', title: i18n.subscri, icon: 'icon-subscribe', act: "SubscribeRecipe('" + id + "',0)"});
  
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
      row_str.push('<img alt="' + i18n.fulltext + '" src="static/fulltext.gif" border="0" />');
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
    hamb_arg.push({klass: 'btn-A', title: i18n.delete, icon: 'icon-delete', act: "DeleteCustomRss('" + id + "','" + title + "')"});
    hamb_arg.push({klass: 'btn-B', title: i18n.share, icon: 'icon-share', act: "StartShareRss('" + title + "', '" + url + "', " + isfulltext + ")"});
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
    if (recipe_id.startsWith("uploaded:")) {
      row_str.push('<i class="iconfont icon-upload icon-as-tag"></i>' + title);
    } else {
      row_str.push(title);
    }
    if (separated) {
      row_str.push('<img alt="' + i18n.separated + '" src="static/separate.gif" border="0" />');
    }
    row_str.push('</div><div class="summaryRow">');
    if (desc.length > 100) {
      row_str.push(desc.substring(0, 100) + '...');
    } else {
      row_str.push(desc);
    }
    row_str.push('</div>');

    hamb_arg = [];
    //汉堡按钮弹出菜单代码
    //if (need_subs && need_subs != 'no' && need_subs != 'false' && need_subs != 0) {
        hamb_arg.push({klass: 'btn-B', title: i18n.subscriptionInfo, icon: 'icon-key', act: "AskForSubscriptionInfo('" + recipe_id + "', '" + recipe.account + "')"});
    //}
    hamb_arg.push({klass: 'btn-A', title: i18n.unsubscribe, icon: 'icon-unsubscribe', act: "UnsubscribeRecipe('" + recipe_id + "','" + title + "')"});
    row_str.push(AddHamburgerButton(hamb_arg));
    row_str.push('</div>');
    //console.log(row_str.join(''));
    var $new_item = $(row_str.join(''));
    $div.append($new_item);
  }
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
        //订阅后跳转到已订阅区段
        $("html, body").animate({scrollTop: $("#mysubscribed").offset().top}, {duration:500, easing:"swing"});
      }
    } else {
      alert(i18n.cannotSubsRecipe + resp.status);
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
    } else {
      alert(i18n.cannotUnsubsRecipe + data.status);
    }
  });
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
  
  $.post("/customrss/delete", {rssid: rssid}, function (data) {
    if (data.status == "ok") {
      for (var idx = 0; idx < my_custom_rss_list.length; idx++) {
        if (my_custom_rss_list[idx].id == rssid) {
          my_custom_rss_list.splice(idx, 1);
          break;
        }
      }
      PopulateMyCustomRss();
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
        my_custom_rss_list.unshift({title: data.title, url: data.url, 'id': data.rssid, isfulltext: data.isfulltext});
        PopulateMyCustomRss();
        title_to_add.val("");
        url_to_add.val("");
      } else {
        alert(i18n.cannotAddRss + data.status);
      }
    },
  );
}

//Global variable
var g_rss_categories = false;

//将一个自定义RSS分享到服务器
function ShareRssToServer(category, title, feedUrl, isfulltext, lang) {
  $.post("/library", {category: category, title: title, url: feedUrl, isfulltext: isfulltext, lang: lang, creator: window.location.hostname}, function (data) {
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
      var modal = new tingle.modal({footer: true});
      modal.setContent('<p>' + i18n.thankForShare + '</p>');
      modal.addFooterBtn(i18n.close, 'actionButton', function() {
        modal.close();
      });
      modal.open();
    } else {
      alert(data.status);
    }
  });
}

//显示一个分享自定义RSS的对话框
function ShowShareDialog(title, feedUrl, isfulltext){
  var all_languages = ['aa','ab','af','ak','sq','am','ar','an','hy','as','av','ae','ay','az','ba','bm','eu','be','bn','bh','bi','bo','bs','br','bg','my','ca','cs','ch','ce','zh','cu','cv','kw','co','cr','cy','cs','da','de','dv','nl','dz','el','en','eo','et','eu','ee','fo','fa','fj','fi','fr','fy','ff','ga','de','gd','ga','gl','gv','el','gn','gu','ht','ha','he','hz','hi','ho','hr','hu','hy','ig','is','io','ii','iu','ie','ia','id','ik','is','it','jv','ja','kl','kn','ks','ka','kr','kk','km','ki','rw','ky','kv','kg','ko','kj','ku','lo','la','lv','li','ln','lt','lb','lu','lg','mk','mh','ml','mi','mr','ms','mi','mk','mg','mt','mn','mi','ms','my','na','nv','nr','nd','ng','ne','nl','nn','nb','no','oc','oj','or','om','os','pa','fa','pi','pl','pt','ps','qu','rm','ro','ro','rn','ru','sg','sa','si','sk','sk','sl','se','sm','sn','sd','so','st','es','sq','sc','sr','ss','su','sw','sv','ty','ta','tt','te','tg','tl','th','bo','ti','to','tn','ts','tk','tr','tw','ug','uk','ur','uz','ve','vi','vo','cy','wa','wo','xh','yi','yo','za','zh','zu'];
  var languages = ['en','fr','zh','es','pt','de','it','ja','ru','tr','ko','ar','cs','nl','el','hi','ms','bn','fa','ur','sw','vi','pa','jv','tl','ha'];
  var modal = new tingle.modal({footer:true});
  var ostr = ['<h2>' + i18n.shareLinksHappiness + '</h2>'];
  ostr.push('<div class="pure-g">');
  ostr.push('<div class="pure-u-1-2"><p>' + i18n.category + '</p></div>');
  ostr.push('<div class="pure-u-1-2"><p>' + i18n.language + '</p></div>');
  ostr.push('</div>');
  ostr.push('<div class="pure-g">');
  ostr.push('<div class="pure-u-1-2"><div class="select-editable"><select onchange="this.nextElementSibling.value=this.value"><option value=""></option>');
  for (var idx in g_rss_categories){
    ostr.push('<option value="' + g_rss_categories[idx] + '">' + g_rss_categories[idx] + '</option>');
  }
  ostr.push('</select><input type="text" name="category" value="" id="txt_share_rss_category" /></div></div>');
  ostr.push('<div class="pure-u-1-2"><div class="select-editable"><select onchange="this.nextElementSibling.value=this.value"><option value=""></option>');
  for (var idx in languages){
    ostr.push('<option value="' + languages[idx] + '">' + languages[idx] + '</option>');
  }
  ostr.push('</select><input type="text" name="category" value="' + BrowserLanguage() + '" id="txt_share_rss_lang" /></div></div>');
  ostr.push('</div>');
  ostr.push('<p>' + i18n.shareCatTips + '</p>');

  modal.setContent(ostr.join(''));
  modal.addFooterBtn(i18n.cancel, 'actionButton', function() {
    modal.close();
  });
  modal.addFooterBtn(i18n.share, 'actionButton act', function() {
    var category = $("#txt_share_rss_category").val();
    var lang = $("#txt_share_rss_lang").val().toLowerCase();
    if (all_languages.indexOf(lang) != -1) {
      ShareRssToServer(category, title, feedUrl, isfulltext, lang);
      modal.close();
    } else {
      alert(i18n.langInvalid);
    }
  });
  modal.open();
}

//点击分享自定义RSS
function StartShareRss(title, feedUrl, isfulltext) {
  //从服务器获取分类信息
  if (!g_rss_categories){
    $.get("/library/category", function(data) {
      if (data.status == "ok") {
        g_rss_categories = data.categories;
        ShowShareDialog(title, feedUrl, isfulltext);
      } else {
        alert(i18n.cannotAddRss + data.status);
      }
    });
  }else{
    ShowShareDialog(title, feedUrl, isfulltext);
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

          modal = new tingle.modal({footer: true});
          modal.setContent('<h2>' + i18n.congratulations + '</h2><p>' + i18n.recipeUploadedTips + '</p>');
          modal.addFooterBtn(i18n.close, 'actionButton', function() {
            modal.close();
          });
          modal.open();
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
    } else {
      alert(data.status);
    }
  });
}

///[end] my.html使用的js部分

///[start] advdelivernow.html使用的部分
//根据选择推送的订阅信息，更新接下来要访问服务器的链接参数，使用get而不使用post是因为gae的cron支持get访问
function UpdateDeliverRecipeLink() {
  var recipeIds = [];
  $("input[type='checkbox']").each(function() {
    if ($(this).is(":checked")) {
      recipeIds.push($(this).prop('id').replace(':', "__"));
    }
    deliverButton.href = "/deliver?u={{session.get('userName', '')}}&id=" + recipeIds.join(',');
  });
}

function SelectDeliverAll() {
  $("input[type='checkbox']").each(function() {
    $(this).prop('checked', true);
  });
};

function SelectDeliverNone() {
  $("input[type='checkbox']").each(function() {
    $(this).prop('checked', false);
  });
};
///[end] advdelivernow.html使用的部分
