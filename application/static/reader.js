//The Kindle browser, especially on older versions of Kindle, supports only limited features.
//If you need to make some changes,
//Please use legacy JavaScript syntax only, avoid using any modern syntax and feature.
//
//此文件有两套滚动方案，每次iframe加载时决定(见iframeLoadEvent)：
//  外层滚动方案(旧方案)：iframe撑开为内容全高，由外层#content滚动翻页，需要测量内容高度。
//    使用者：窄屏/触屏(isMobile())、墨水屏/嵌入式浏览器(isEinkBrowser())、
//    以及运行时探测到不支持iframe内部滚动的浏览器(整个会话自动回退)。
//    注意不能仅按宽度判断：Kindle可横屏，还有大屏墨水屏阅读器/平板等。
//  iframe内部滚动方案(新方案)：iframe固定为视口高度，由iframe文档原生滚动，
//    滚动范围由浏览器自己维护，不测量内容高度，
//    彻底规避Chrome计算iframe内容高度不准导致内容截断的问题(issue #698)。

var g_iframeScrollHeight = 500; //在 iframeLoadEvent 里更新
//var g_iframeClientHeight = 500;
var g_currentArticle = {}; //{title:,src:,}
var g_dictMode = false; //当前是否处于查词模式
const g_trTextContainerHeight = 350; //350px在reader.css定义tr-text-container和tr-result-text
var g_navWidth = 400; //PC端左侧导航栏宽度
var g_lastNavWidth = 400; //用于双击恢复展开的宽度
var g_legacyScroll = isMobile() || isEinkBrowser(); //当前文章是否使用外层滚动方案(旧方案)，每次iframe加载时重算
var g_innerScrollBroken = false; //探测到浏览器不支持iframe内部滚动后置位，整个会话不再尝试新方案
var g_innerScrollVerified = false; //探测确认浏览器支持iframe内部滚动后置位，避免重复探测打扰阅读位置
var g_pageHeight = 0; //校准后的页面可视高度，0表示未校准(见calibratePageHeight)
var g_heightCalibrated = false; //本次窗口尺寸下是否已完成校准
var g_lastMobileState = null; //上次adjustContentHeight时是否为移动宽度，用于检测宽度跨越1072边沿
var g_bottomMargin = 40; //触屏/墨水屏设备底部预留像素：部分设备(如Kindle)浏览器自带界面
                          //遮挡页面底部且遮挡量无法编程测量，固定预留40px保证底部元素完整可见

//对古董浏览器兼容性最好的判断一个变量是否为空的语法
//支持基本类型/数组/对象
function isEmpty(obj) {
  if (!obj) {
    return true;
  }
  if (Object.prototype.toString.call(obj) == '[object Array]') {
    return obj.length == 0;
  }
  for (var key in obj) {
    if (obj.hasOwnProperty(key)) {
      return false;
    }
  }
  return true;
}

//将一个字符串转义为能安全用于js字符串拼接的场合
function encodeJsSafeStr(str) {
  return btoa(encodeURIComponent(str));
}

//安全的解码经过 encodeJsSafeStr 编码的字符串
function decodeJsSafeStr(str) {
  return decodeURIComponent(atob(str));
}

//将一个字典对象转换为ajax使用的参数字符串
function formatParams(data) {
  var arr = [("v_=" + Math.random()).replace(".", "")];
  for (var name in data) {
    arr.push(encodeURIComponent(name) + "=" + encodeURIComponent(data[name]));
  }
  return arr.join("&");
}

//封装ajax，在Kindle简陋的浏览器中使用，尽量使用原生js功能
//ajax({
//    url: "url",
//    type: "POST",
//    data: {},
//    dataType: "json",   //optional,'json'/'text'/'xml'
//    success: function (resp, xml) {},
//    error: function (xhr, status, error) {} //optional
//});
function ajax(url, options) {
  if (typeof url == 'object') { // 兼容两种参数形式
    options = url;
    url = options.url;
  }
  options = options || {};
  var type = (options.type || "GET").toUpperCase();
  var dataType = (options.dataType || "json").toLowerCase();
  var params = formatParams(options.data || {});
  var xhr = new XMLHttpRequest();
  xhr.onreadystatechange = function () {
    if (xhr.readyState == 4) {
      var status = xhr.status;
      if ((status >= 200) && (status < 300)) {
        var resp = (dataType == "json") ? JSON.parse(xhr.responseText) : xhr.responseText;
        options.success && options.success(resp, xhr.responseXML);
      } else if (options.error) {
        options.error(xhr, status, xhr.statusText);
      }
    }
  }

  if (type == "GET") {
    xhr.open("GET", url + "?" + params, true); //第三个参数true表示异步请求
    xhr.send(null);
  } else if (type == "POST") {
    xhr.open("POST", url, true);
    xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
    xhr.send(params);
  }
}

//兼容 jQuery 的 get 函数
function ajax_get(url, data, success, dataType) {
  if (typeof data == 'function') {
    dataType = dataType || success;
    success = data;
    data = {};
  }
  ajax({url: url, type: 'GET', data: data, success: success, dataType: dataType});
}

// 兼容 jQuery 的 post 函数
function ajax_post(url, data, success, dataType) {
  if (typeof data == 'function') {
    dataType = dataType || success;
    success = data;
    data = {};
  }
  ajax({url: url, type: 'POST', data: data, success: success, dataType: dataType});
}


//获取当前文章iframe的文档对象，失败返回null
function getIframeDoc() {
  var iframe = document.getElementById('iframe');
  if (!iframe) {
    return null;
  }
  try {
    return iframe.contentDocument || iframe.contentWindow.document;
  } catch (e) {
    return null;
  }
}

//将焦点交还给文章iframe
//部分Chrome版本在点击/拖拽父页面元素(导航栏/分隔条等)后，不再把滚轮事件路由给iframe，
//表现为文章无法滚动，必须点击一下内容区才恢复，这里在相关交互后显式聚焦规避
//仅iframe内部滚动方案需要，外层滚动方案(旧方案)的滚轮始终作用于父页面，保持原行为
function focusIframe() {
  if (g_legacyScroll) {
    return;
  }
  try {
    var ifr = document.getElementById('iframe');
    if (ifr && ifr.contentWindow) {
      ifr.contentWindow.focus();
    }
  } catch (e) {}
}

//读取iframe文档当前的滚动位置，兼容标准模式和quirks模式
function iframeScrollTop(doc) {
  if (!doc || !doc.documentElement) {
    return 0;
  }
  return doc.documentElement.scrollTop || (doc.body ? doc.body.scrollTop : 0) || 0;
}

//设置iframe文档的滚动位置
function iframeScrollTo(doc, top) {
  if (!doc || !doc.documentElement) {
    return;
  }
  doc.documentElement.scrollTop = top;
  if (doc.body) {
    doc.body.scrollTop = top;
  }
}

//返回iframe文档内容的总高度
function iframeScrollHeight(doc) {
  if (!doc || !doc.documentElement) {
    return 0;
  }
  return Math.max(doc.documentElement.scrollHeight, doc.body ? doc.body.scrollHeight : 0);
}

//返回iframe文档可视区域的高度
//注意不能使用documentElement.clientHeight作为首选：
//webshelf里的文章由lxml序列化，没有DOCTYPE声明，浏览器以quirks模式渲染，
//此时documentElement.clientHeight返回整个文档高度而非视口高度，
//会导致pageDown误判已在页末而直接跳到下一篇文章
//contentWindow.innerHeight是嵌套视口的精确高度，与渲染模式无关
function iframeClientHeight(doc) {
  if (!doc || !doc.documentElement) {
    return 0;
  }
  var win = doc.defaultView;
  if (win && win.innerHeight) {
    return win.innerHeight;
  }
  var ifr = document.getElementById('iframe');
  if (ifr && ifr.clientHeight) {
    return ifr.clientHeight;
  }
  return doc.body ? (doc.body.clientHeight || doc.documentElement.clientHeight) : doc.documentElement.clientHeight;
}

//探测iframe文档是否真的可以内部滚动
//尝试设置scrollTop后读回非零值即认为支持，仅对内容超出视口的文档有意义
function innerScrollWorks(doc) {
  try {
    //避免smooth滚动导致读回旧值(quirks模式下滚动元素是body，两处都设置)
    doc.documentElement.style.scrollBehavior = 'auto';
    doc.body.style.scrollBehavior = 'auto';
    doc.documentElement.scrollTop = 30;
    doc.body.scrollTop = 30;
    var ok = (doc.documentElement.scrollTop > 0) || (doc.body.scrollTop > 0);
    doc.documentElement.scrollTop = 0;
    doc.body.scrollTop = 0;
    return ok;
  } catch (e) {
    return false;
  }
}

//获取当前滚动信息，统一封装两种滚动方案
//外层滚动方案(旧方案)滚动#content，iframe内部滚动方案(新方案)滚动iframe文档
//返回null表示iframe文档尚不可用
function getScrollInfo() {
  if (g_legacyScroll) {
    var content = document.getElementById('content');
    return {
      scrollTop: content.scrollTop,
      scrollHeight: content.scrollHeight,
      clientHeight: content.clientHeight,
      scrollTo: function (top) { content.scrollTop = top; }
    };
  }

  var doc = getIframeDoc();
  if (!doc) {
    return null;
  }
  return {
    scrollTop: iframeScrollTop(doc),
    scrollHeight: iframeScrollHeight(doc),
    clientHeight: iframeClientHeight(doc),
    scrollTo: function (top) { iframeScrollTo(doc, top); }
  };
}

//更新页面位置指示器
function updatePosIndicator() {
  var indicator = document.getElementById('pos-indicator');
  var info = getScrollInfo();
  if (!info) {
    return;
  }
  var height = info.clientHeight;
  var scrollable = info.scrollHeight - height;
  var ratio = scrollable > 0 ? info.scrollTop / scrollable : 0;
  var indiHeight = 50;
  var pos = ratio * (height - indiHeight);
  pos = Math.min(pos, height - indiHeight - 5); //5是稍离开屏幕下沿
  indicator.style.top = pos + 'px';
}

//更新导航栏位置指示器
function updateNavIndicator() {
  var content = document.getElementById('nav-content');
  var indicator = document.getElementById('nav-indicator');
  if (!indicator) {
    return;
  }
  var height = content.clientHeight;
  var scrollTop = content.scrollTop;
  var scrollHeight = content.scrollHeight - height;
  var ratio = scrollHeight ? scrollTop / scrollHeight : 0;
  var indiHeight = 30;
  var pos = ratio * (height - indiHeight);
  if (isMobile()) {
    pos = Math.min(pos, height - indiHeight - 80); //80是下部工具栏高度
  } else {
    pos = Math.min(pos, height - indiHeight - 5); //5是稍离开屏幕下沿
  }
  indicator.style.top = pos + 'px';
}

//获取最靠近点击位置的一个单词（以空格分隔的单词）
function getWordAtClick(event, iframe) {
  iframe = iframe || document.getElementById('iframe');
  var doc = iframe.contentDocument || iframe.contentWindow.document;
  var range = doc.caretRangeFromPoint(event.clientX, event.clientY);
  if (range) {
    var textNode = range.startContainer;
    var offset = range.startOffset;
    if (textNode.nodeType == Node.TEXT_NODE) {
      var textContent = textNode.textContent;
      var leftText = textContent.slice(0, offset);
      var rightText = textContent.slice(offset);
      var clickedChar = textContent.charAt(offset);
      var isCJK = /[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]/.test(clickedChar);
      var isCJKPunctuation = /[\u3000-\u303F\uFF00-\uFFEF]/.test(clickedChar);
      if (isCJK || isCJKPunctuation) {
        return clickedChar;
      }

      //var leftMatch = leftText.match(/\p{L}+$/u); //kindle不支持 "\p{L}"
      //var rightMatch = rightText.match(/^\p{L}+/u);
      var unicodeLetters = "\u0041-\u005A\u0061-\u007A\u00AA\u00B5\u00BA\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u01BF\u01CD-\u01FF\u0620-\u064A";
      var patLeft = new RegExp("[" + unicodeLetters + "]+$");
      var patRight = new RegExp("^[" + unicodeLetters + "]+");
      var leftMatch = leftText.match(patLeft);
      var rightMatch = rightText.match(patRight);
      if (leftMatch || rightMatch) {
        return (leftMatch ? leftMatch[0] : '') + (rightMatch ? rightMatch[0] : '');
      }
    }
  }
  return '';
}

//连接服务器查询一个单词的释义然后显示出来
//word: 要查的词
//selection: 是否有选择区域
function translateWord(word, selection) {
  var language = isEmpty(g_currentArticle) ? '' : getBookLanguage(g_currentArticle);
  ajax_post('/reader/dict', {word: word, language: language}, function (resp) {
    if (resp.status == 'ok') {
      showDictDialog(resp.word, resp.definition, resp.dictname, resp.others);
      if (selection) {
        selection.removeAllRanges();
      }
    } else {
      alert(resp.status);
    }
  });
}

//在查词窗口选择其他词典，则使用其他词典再次翻译
function changeDictToTranslate(event) {
  event.stopPropagation();
  event.preventDefault();
  var sel = document.getElementById('tr-dict-name-sel');
  var value = sel ? sel.value : '';
  if (!value) {
    return;
  }
  value = decodeJsSafeStr(value).split('::');
  var word = value[0];
  var language = value[1];
  var engine = value[2];
  var database = value[3];
  ajax_post('/reader/dict', {word: word, language: language, engine: engine, database: database}, function (resp) {
    if (resp.status == 'ok') {
      showDictDialog(resp.word, resp.definition, resp.dictname, resp.others);
    } else {
      alert(resp.status);
    }
  });
}

//显示查词窗口
//word, text - 分别为单词和释义
//dictname: 返回当前释义的词典名字
//others: 其他候选词典列表 [{language:,engine:,database:,dbName}]
function showDictDialog(word, text, dictname, others) {
  var content = document.getElementById('content');
  var dialog = document.getElementById('tr-result');
  var dictNameDiv = document.getElementById('tr-dict-name-sel');
  var titleDiv = document.getElementById('tr-word');
  var textWrap = document.getElementById('tr-text-container');
  var textDiv = document.getElementById('tr-text');
  //候选词典下拉列表
  var ostr = ['<option value="">▽ ' + (dictname || '') + '</option>'];
  for (var i = 0; i < others.length; i++) {
    var elem = others[i];
    if (elem.language && elem.engine && elem.database) {
      var value = encodeJsSafeStr(word + '::' + elem.language + '::' + elem.engine + '::' + elem.database);
      var dbName = elem.dbName;
      if (dbName.length < 15) {
        dbName = elem.engine + ' [' + dbName + ']';
      }
      ostr.push('<option value="' + value + '">' + elem.dbName + '</option>');
    }
  }
  dictNameDiv.innerHTML = ostr.join('');
  titleDiv.innerHTML = word;
  text = text ? text.replace(/\n/g, '<br/>') : '';
  if (textDiv.attachShadow) { //使用shadow dom技术可以隔离css
    if (!textDiv.shadowRoot) { //在第一个执行attachShadow后，这个变量会自动被设置
      textDiv.attachShadow({mode: 'open'});
      textDiv.shadowRoot.addEventListener('click', closeDictDialog);
      //console.log('This browser supports Shadow DOM.');
    }
    textDiv.shadowRoot.innerHTML = text;
  } else {
    textDiv.innerHTML = text;
  }
  textDiv.style.textAlign = text.length > 50 ? 'left' : 'center';
  var y = Math.max(event.clientY - content.scrollTop, 0);
  var height = content.clientHeight;
  if (y > height * 0.6) {
    dialog.style.top = 'auto';
    dialog.style.bottom = Math.max(height - y, 40) + 'px';
  } else {
    dialog.style.bottom = 'auto';
    dialog.style.top = (y + 20) + 'px';
  }
  dialog.style.display = 'block';
  textWrap.scrollTop = 0;
  //根据情况确定是否显示上下翻页按钮
  var scrlUp = document.getElementById('tr-scrl-up-icon');
  var scrlDown = document.getElementById('tr-scrl-down-icon');
  if (isMobile() && (textWrap.scrollHeight > g_trTextContainerHeight)) {
    scrlUp.style.display = 'block';
    scrlDown.style.display = 'block';
    textDiv.style.paddingRight = '40px';
  } else {
    scrlUp.style.display = 'none';
    scrlDown.style.display = 'none';
    textDiv.style.paddingRight = '10px';
  }
}

//关闭查词窗口
function closeDictDialog(event) {
  //点击了一个单词链接，处理词条跳转
  var target = event ? event.target || event.srcElement : null;
  if (target && (target.tagName == 'A')) {
    event.stopPropagation();
    event.preventDefault();
    var href = target.getAttribute('href') || '';
    if (href.indexOf('https://kindleear/entry/') == 0) {
      var word = href.substring(24);
      if (word) {
        translateWord(word);
        return false;
      }
    } else if (href && g_allowLinks) {
      openLinkInNewTab(href);
    }
  }

  g_dictMode = false;
  var textDiv = document.getElementById('tr-text');
  if (!textDiv.shadowRoot) { //如果是shadow dom，则不清除之前的翻译，让下一次的CSS渲染快一点
    textDiv.innerHTML = '';
  }
  document.getElementById('tr-result').style.display = 'none';
  document.getElementById('corner-dict-hint').style.display = 'none';
}

//查词窗口向上滚动
function dictScrollUp(event) {
  event.stopPropagation();
  var textWrap = document.getElementById('tr-text-container');
  textWrap.scrollTop = Math.max(0, textWrap.scrollTop - g_trTextContainerHeight + 40);
}

//查词窗口向下滚动
function dictScrollDown(event) {
  event.stopPropagation();
  var textWrap = document.getElementById('tr-text-container');
  textWrap.scrollTop = Math.min(textWrap.scrollHeight, textWrap.scrollTop + g_trTextContainerHeight - 40);
}

//屏幕点击事件的处理
function clickEvent(event) {
  event.preventDefault();
  var content = document.getElementById('content');
  var navbar = document.getElementById('navbar');
  var navPopMenu = document.getElementById('nav-popmenu');
  var x = event.clientX;
  var y = event.clientY - content.scrollTop;
  var ww = content.clientWidth;
  var wh = content.clientHeight;
  //alert(x + ',' + event.clientY + ',' + content.scrollTop + ',' + content.clientHeight);
  navPopMenu.style.display = 'none';
  if (y < wh / 5) { //上部 (20%)
    if (x < ww * 0.15) { //左上 15%，上一篇文章或直接激活查词模式
      if (g_topleftDict) {
        toggleDictMode();
      } else {
        openPrevArticle();
      }
    } else if (x > ww * 0.8) { //右上 20%，下一篇文章
      openNextArticle();
    } else if (isMobile()) { //中间65%，弹出菜单
      navbar.style.display = (navbar.style.display == "block") ? "none" : "block";
    }
  } else if ((x < ww / 5) && (y < wh * 0.7)) { //左侧往回翻页 (宽20%,高50%)
    pageUp(content, navbar);
  } else { //右侧往前翻页
    pageDown(content, navbar, event.ctrlKey || event.metaKey);
  }
}

//往上翻页
function pageUp(content, navbar) {
  content = content || document.getElementById('content');
  navbar = navbar || document.getElementById('navbar');
  if (isMobile() && (navbar.style.display == "block")) {
    navbar.style.display = 'none';
  } else if (g_inkMode) {
    var info = getScrollInfo();
    if (!info) {
      openPrevArticle();
    } else if (info.scrollTop <= 1) {
      openPrevArticle();
    } else {
      info.scrollTo(Math.max(0, info.scrollTop - info.clientHeight + 40));
    }
  }
}

//禁用事件的默认处理事件
function eventPreventDefault(event) {
  event.preventDefault();
}

//往下翻页
//所有参数都是可选的
function pageDown(content, navbar, ctrlKey) {
  content = content || document.getElementById('content');
  navbar = navbar || document.getElementById('navbar');
  if (isMobile() && (navbar.style.display == "block")) {
    navbar.style.display = 'none';
  } else if (g_inkMode) {
    if (g_legacyScroll) {
      //外层滚动方案(旧方案，保持原有行为)
      var iframe = document.getElementById('iframe');
      var iframeHeight = parseInt(iframe.style.height);
      var scrollTop = content.scrollTop;
      var scrollHeight = g_iframeScrollHeight || content.scrollHeight;

      //已经到页末, -2是考虑浮点误差，其实-1就可以
      if (scrollTop >= scrollHeight - content.clientHeight - 2) {
        //规避chrome的iframe高度计算不准的bug，使用Ctrl+Click手动扩展iframe高度
        if (ctrlKey && iframeHeight) {
          var newHeight = iframeHeight + 200; //每次增长200px
          iframe.style.height = newHeight + 'px';
          g_iframeScrollHeight = newHeight;
          content.scrollTop = newHeight;
        } else {
          openNextArticle();
        }
      } else if (ctrlKey) { //跳到页末
        content.scrollTop = scrollHeight;
      } else { //翻页
        content.scrollTop = Math.min(scrollTop + content.clientHeight - 40, scrollHeight);
      }
    } else {
      //iframe内部滚动方案(新方案)，滚动范围由浏览器原生维护，内容不会被截断
      var info = getScrollInfo();
      if (!info) {
        openNextArticle();
        return;
      }

      //已经到页末, -2是考虑浮点误差，其实-1就可以
      if (info.scrollTop >= info.scrollHeight - info.clientHeight - 2) {
        openNextArticle();
      } else if (ctrlKey) { //跳到页末
        info.scrollTo(info.scrollHeight);
      } else { //翻页
        info.scrollTo(Math.min(info.scrollTop + info.clientHeight - 40, info.scrollHeight));
      }
    }
  }
}

//iframe发送过来的消息，配合reader-inject.js使用，初始版本使用，现已废弃
//初始版本的方案是在iframe中注入脚本，和主页面互发消息，可以跨域使用，但是增加了复杂性
//现在版本直接操纵iframe页面，python代码和js代码都更简单，但是不能跨域
function iFrameEvent_Deprecated(event) {
  var data = event.data;
  //console.log('iFrameEvent: ' + JSON.stringify(data));
  g_iframeScrollHeight = data.scrollHeight;
  //g_iframeClientHeight = data.clientHeight;
  if (data.type == 'iframeLoaded') {
    document.getElementById('iframe').style.height = g_iframeScrollHeight + 'px';
  } else if (data.type == 'click') {
    if (data.href && g_allowLinks) {
      openLinkInNewTab(data.href);
    } else {
      clickEvent(data.event);
    }
  }
}

//自适应在新tab中打开链接
function openLinkInNewTab(url) {
  if (window.open) {
    window.open(url, '_blank');
  } else {
    window.location.href = url;
  }
}

//返回屏幕宽度
function getViewportWidth() {
  return window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth;
}

//判断是否是移动设备，包括Kindle设备，如果要修改这个函数，请同步修改reader.css
//传统6寸墨水屏分辨率(800x600)
//pw3/pw4/voyage的分辨率(1448x1072)
//oasis分辨率(1680x1264)
//pw5分辨率(1648x1236)
function isMobile() {
  var width = window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth;
  return width <= 1072;
}

//判断是否为墨水屏设备或老旧的嵌入式浏览器
//这类设备一律使用外层滚动方案(旧方案)，即使横屏或大屏导致isMobile()为false也一样
//注意不能只靠宽度判断：Kindle可以横屏，还有大屏墨水屏阅读器、平板、越狱后安装的其他浏览器等
function isEinkBrowser() {
  var ua = navigator.userAgent || '';
  return /kindle|silk|kobo|boox|onyx|pocketbook|remarkable|netfront|eink/i.test(ua);
}

//决定当前是否使用外层滚动方案(旧方案)
function shouldUseLegacyScroll() {
  return isMobile() || isEinkBrowser() || g_innerScrollBroken;
}

//返回页面可视区域高度
//墨水屏浏览器上此值经过校准(见calibratePageHeight)，因为innerHeight/clientHeight
//可能比实际可视区域大；触屏/墨水屏设备再扣除底部预留g_bottomMargin，
//避免浏览器自带界面遮挡页面底部(如Kindle导航栏底部按钮被截断)
function getViewportHeight() {
  var h = (g_pageHeight > 0) ? g_pageHeight : Math.min(document.documentElement.clientHeight, window.innerHeight || 0);
  if (isMobile() || isEinkBrowser()) {
    h -= g_bottomMargin;
  }
  return Math.max(200, h);
}

//点击日期行，打开或折叠此日期内的书本
function toggleNavDate(nav) {
  var toggleIcon = nav.querySelector('.tree-icon');
  toggleIcon.textContent = (toggleIcon.textContent == "▾") ? "▸" : "▾";
  var items = nav.parentNode.querySelectorAll('.nav-book');
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    item.style.display = (item.style.display == "block") ? "none" : "block";
  }
  hidePopMenu();
}

//点击书本行，打开或折叠此书本内的文章
function toggleNavBook(nav) {
  var subNav = nav.querySelector('.nav-article');
  if (subNav) {
    subNav.style.display = (subNav.style.display == "block") ? "none" : "block";
  }
  hidePopMenu();
}

//Kindle浏览器有诸多限制，需要使用这个函数来调整一些元素的高度
function adjustContentHeight() {
  var mobileNow = isMobile();
  if (g_lastMobileState === false && mobileNow) {
    //从PC宽度缩到移动宽度：清除导航栏的内联display(优先级高于CSS媒体查询)，
    //让媒体查询自动隐藏左侧导航栏；手机上仅地址栏伸缩触发的resize不会走到这里
    var nb = document.getElementById('navbar');
    if (nb) {
      nb.style.display = '';
    }
  }
  g_lastMobileState = mobileNow;

  if (g_pageHeight <= 0) {
    //先按原始viewport值布置一次，给校准探测提供一个可参照的布局
    g_pageHeight = Math.min(document.documentElement.clientHeight, window.innerHeight || 0);
  }

  var content = document.getElementById('content');
  var container = document.getElementById('container');
  var navbar = document.getElementById('navbar');
  var navContent = document.getElementById('nav-content');
  var footer = document.getElementById('nav-footer');
  var resizer = document.getElementById('nav-resizer');
  setInkMode(g_inkMode);
  if (isMobile()) {
    if (resizer) {
      resizer.style.display = 'none';
    }
    if (navbar) {
      navbar.style.width = '';
      //显式设置高度：部分浏览器把fixed元素bottom:0解析到虚报的视口底部，
      //导致导航栏弹出后底部工具栏按钮只显示一半
      navbar.style.height = getViewportHeight() + 'px';
    }
    if (container) {
      container.style.marginLeft = '';
    }
  } else {
    if (navbar) {
      navbar.style.height = '';
    }
    if (resizer) {
      resizer.style.display = 'block';
    }
    if (g_navWidth <= 0) {
      if (navbar) {
        navbar.style.display = 'none';
        navbar.style.width = '0px';
      }
      if (resizer) {
        resizer.style.left = '0px';
      }
      if (container) {
        container.style.marginLeft = (resizer ? resizer.offsetWidth || 6 : 6) + 'px';
      }
    } else {
      if (navbar) {
        navbar.style.display = 'block';
        navbar.style.width = g_navWidth + 'px';
      }
      if (resizer) {
        resizer.style.left = g_navWidth + 'px';
      }
      if (container) {
        container.style.marginLeft = (g_navWidth + (resizer ? resizer.offsetWidth || 6 : 6)) + 'px';
      }
    }
  }
  if (navbar && navbar.offsetHeight && footer && footer.offsetHeight) {
    navContent.style.height = (navbar.offsetHeight - footer.offsetHeight) + 'px';
  }
  if (container) {
    container.style.height = getViewportHeight() + 'px';
  }
  if (isMobile() || isEinkBrowser()) {
    //文档盒高度显式设为校准值(小于虚报视口)：
    //部分内核在文档高度等于视口时也渲染滚动条槽，小于后彻底不画
    document.documentElement.style.height = getViewportHeight() + 'px';
    document.body.style.height = getViewportHeight() + 'px';
  } else {
    document.documentElement.style.height = '';
    document.body.style.height = '';
  }
  if (content) {
    content.style.height = getViewportHeight() + 'px';
    //新方案由iframe内部滚动，外层不再滚动，避免出现双层滚动条
    content.style.overflowY = g_legacyScroll ? 'auto' : 'hidden';
  }
  if (!g_legacyScroll) {
    var ifr = document.getElementById('iframe');
    if (ifr) {
      ifr.style.height = (getViewportHeight() + 40) + 'px';
    }
  }

  if (g_legacyScroll && (isMobile() || isEinkBrowser())) {
    //老内核(如Kindle的WebKit534)不支持::-webkit-scrollbar隐藏滚动条，
    //且可能无视scrolling="no"和内层overflow:hidden，给iframe自身画滚动条。
    //把#content和iframe都加宽20px，让两者的滚动条都落到container(overflow:hidden)
    //之外被裁掉；内层body右边距相应加大(见adjustIFrameStyle)，保证文字不进入被裁区域
    if (container && content) {
      container.style.overflow = 'hidden';
      content.style.width = (container.clientWidth + 20) + 'px';
      var ifr2 = document.getElementById('iframe');
      if (ifr2) {
        ifr2.style.width = (container.clientWidth + 20) + 'px';
      }
    }
  } else {
    if (container) {
      container.style.overflow = '';
    }
    if (content) {
      content.style.width = '';
    }
    var ifr3 = document.getElementById('iframe');
    if (ifr3) {
      ifr3.style.width = '';
    }
  }

  if (!g_heightCalibrated) {
    g_heightCalibrated = true;
    calibratePageHeight(); //探测真实可视高度，若与当前值不同会更新后重新应用
  }
}

//测量页面最大可滚动距离(兼容各种老引擎的滚动接口)
//先window.scrollTo，读不回值再用scrollTop直接赋值兜底
function measureMaxScroll(html, body) {
  var oldY = window.pageYOffset || 0;
  var oldHtml = html.scrollTop || 0;
  var oldBody = body ? (body.scrollTop || 0) : 0;
  var scrolled = 0;

  window.scrollTo(0, 1000000);
  scrolled = window.pageYOffset || window.scrollY || html.scrollTop || (body ? body.scrollTop : 0) || 0;

  if (scrolled <= 0) {
    html.scrollTop = 1000000;
    if (body) {
      body.scrollTop = 1000000;
    }
    scrolled = html.scrollTop || (body ? body.scrollTop : 0) || 0;
  }

  //还原滚动位置
  window.scrollTo(0, oldY);
  html.scrollTop = oldHtml;
  if (body) {
    body.scrollTop = oldBody;
  }
  return scrolled;
}

//测量页面真实可视高度(不依赖编程式滚动，老内核可能不支持window.scrollTo)
//部分浏览器viewport参数虚报(如Kindle报告1268但底部被浏览器自带界面遮挡)
//方法1: fixed探针——bottom:0的fixed元素相对真实视口定位，其rect.top即真实可视高度
//方法2: elementFromPoint二分——视口之外的点返回null，找出最大可见y
function measureRealViewport() {
  var vh = g_pageHeight;

  //方法1: fixed探针
  try {
    var probe = document.createElement('div');
    probe.style.cssText = 'position:fixed;bottom:0px;left:0px;width:1px;height:1px;visibility:hidden;';
    document.body.appendChild(probe);
    var top = probe.getBoundingClientRect().top;
    document.body.removeChild(probe);
    if ((top > 200) && ((top + 1) < vh - 4)) {
      return top + 1;
    }
  } catch (e) {}

  //方法2: elementFromPoint二分
  try {
    if (document.elementFromPoint) {
      var container = document.getElementById('container');
      if (!container) {
        return 0;
      }
      var oldH = container.style.height;
      container.style.height = '999999px'; //确保探测点下方有内容
      var lo = 300;
      var hi = Math.min(vh + 600, 5000); //真实高度不会大于虚报值太多
      var found = 0;
      if (!document.elementFromPoint(5, hi - 1)) { //hi处应不可见，否则视为无需校准
        while (hi - lo > 2) {
          var mid = Math.floor((lo + hi) / 2);
          if (document.elementFromPoint(5, mid)) {
            lo = mid;
          } else {
            hi = mid;
          }
        }
        found = lo;
      }
      container.style.height = oldH;
      if ((found > 200) && (found < vh - 4)) {
        return found;
      }
    }
  } catch (e) {}

  return 0;
}

//校准页面真实可视高度
//部分墨水屏浏览器(Kindle等)的innerHeight/clientHeight比实际可视区域大
//(包含了浏览器自身界面)，导致设置的高度超出真实屏幕：
//导航栏底部工具栏按钮被截断一半等问题。
//解决办法是利用浏览器自身的滚动机制测量真实可视高度，不受viewport参数虚报影响
function calibratePageHeight() {
  var html = document.documentElement;
  var body = document.body;
  var vh = g_pageHeight;
  var scrollHeight = Math.max(html.scrollHeight, body.scrollHeight);

  if (isMobile() || isEinkBrowser()) {
    var real = measureRealViewport();
    if ((real > 200) && (real < vh)) {
      vh = real;
    }
  } else if (scrollHeight > html.clientHeight + 1) {
    //普通浏览器clientHeight可信，直接按文档溢出量缩减
    vh = Math.max(200, vh - (scrollHeight - html.clientHeight) - 1);
  }

  if (Math.abs(vh - g_pageHeight) > 1) {
    g_pageHeight = vh;
    adjustContentHeight(); //g_heightCalibrated已置位，不会递归校准
  }
}

//设置PC端导航栏宽度及分隔条位置
function setNavWidth(width) {
  if (isMobile()) {
    return;
  }
  var navbar = document.getElementById('navbar');
  var container = document.getElementById('container');
  var resizer = document.getElementById('nav-resizer');
  if (!navbar || !container || !resizer) {
    return;
  }

  var resizerWidth = resizer.offsetWidth || 6;
  var winWidth = window.innerWidth || document.documentElement.clientWidth || 1200;
  var maxAllowed = winWidth - 100;
  if (width < 40) {
    width = 0;
  } else if (width > maxAllowed) {
    width = maxAllowed;
  }

  g_navWidth = width;
  if (width >= 40) {
    g_lastNavWidth = width;
  }

  if (width <= 0) {
    navbar.style.display = 'none';
    navbar.style.width = '0px';
    resizer.style.left = '0px';
    container.style.marginLeft = resizerWidth + 'px';
  } else {
    navbar.style.display = 'block';
    navbar.style.width = width + 'px';
    resizer.style.left = width + 'px';
    container.style.marginLeft = (width + resizerWidth) + 'px';
    var navContent = document.getElementById('nav-content');
    var footer = document.getElementById('nav-footer');
    if (navbar.offsetHeight && footer && footer.offsetHeight) {
      navContent.style.height = (navbar.offsetHeight - footer.offsetHeight) + 'px';
    }
  }

  try {
    localStorage.setItem('ke_nav_width', width);
  } catch (e) {}
}

//初始化PC端导航栏与内容区分隔条拖拽功能
function initNavResizer() {
  var resizer = document.getElementById('nav-resizer');
  var navbar = document.getElementById('navbar');
  var container = document.getElementById('container');
  var iframe = document.getElementById('iframe');
  if (!navbar || !container) {
    return;
  }
  if (!resizer) {
    resizer = document.createElement('div');
    resizer.id = 'nav-resizer';
    resizer.className = 'nav-resizer';
    document.body.appendChild(resizer);
  }

  var isDragging = false;

  resizer.addEventListener('mousedown', function(e) {
    if (isMobile() || (e.button !== 0)) {
      return;
    }
    isDragging = true;
    resizer.className = 'nav-resizer resizing';
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.body.style.webkitUserSelect = 'none';
    if (iframe) {
      iframe.style.pointerEvents = 'none';
    }
    e.preventDefault();
  });

  document.addEventListener('mousemove', function(e) {
    if (!isDragging || isMobile()) {
      return;
    }
    setNavWidth(e.clientX);
  });

  function stopDrag() {
    if (isDragging) {
      isDragging = false;
      resizer.className = 'nav-resizer';
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.body.style.webkitUserSelect = '';
      if (iframe) {
        iframe.style.pointerEvents = 'auto';
        if (g_legacyScroll) { //仅外层滚动方案需要重新测量高度，新方案iframe内部自动重排
          var doc = iframe.contentDocument || iframe.contentWindow.document;
          if (doc && doc.body) {
            iframe.style.height = 'auto';
            recalculateHeight(iframe, doc);
          }
        } else {
          focusIframe(); //拖完分隔条把焦点还给文章，保证滚轮可用
        }
      }
    }
  }

  document.addEventListener('mouseup', stopDrag);
  window.addEventListener('blur', stopDrag);

  resizer.addEventListener('dblclick', function(e) {
    if (isMobile()) {
      return;
    }
    if (g_navWidth <= 0) {
      setNavWidth(g_lastNavWidth > 50 ? g_lastNavWidth : 400);
    } else {
      g_lastNavWidth = g_navWidth;
      setNavWidth(0);
    }
  });

  if (!isMobile()) {
    try {
      var saved = localStorage.getItem('ke_nav_width');
      if (saved !== null) {
        var w = parseInt(saved, 10);
        if (!isNaN(w) && w >= 0) {
          setNavWidth(w);
        }
      }
    } catch (e) {}
  }
}

//导航栏往上翻页
function navPageUp() {
  var navbar = document.getElementById('navbar');
  var navContent = document.getElementById('nav-content');
  var footer = document.getElementById('nav-footer');
  if (navbar.clientHeight && footer.offsetHeight) {
    var height = navbar.clientHeight - footer.offsetHeight - 40;
    navContent.scrollTop = Math.max(navContent.scrollTop - height, 0);
  }
  hidePopMenu();
}

//导航栏往下翻页
function navPageDown() {
  var navbar = document.getElementById('navbar');
  var navContent = document.getElementById('nav-content');
  var footer = document.getElementById('nav-footer');
  if (navbar.clientHeight && footer.offsetHeight) {
    var height = navbar.clientHeight - footer.offsetHeight - 40;
    navContent.scrollTop = Math.min(navContent.scrollTop + height, navContent.scrollHeight);
  }
  hidePopMenu();
}

//关闭导航栏
function navCloseNav() {
  if (isMobile()) {
    hidePopMenu();
    hideNavbar();
  }
}

//导航栏打开或折叠所有项目
//level: 0 - 折叠所有，1 - 打开第一级，2 - 打开第一级和第二级
function navExpandCollapseAll(level) {
  var navContent = document.getElementById('nav-content');
  var items = navContent.querySelectorAll('.tree-icon');
  for (var i = 0; i < items.length; i++) {
    items[i].innerHTML = level ? "▾" : "▸";
  }
  items = navContent.querySelectorAll('.nav-book, .nav-article');
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    var classList = item.classList;
    if (classList.contains('nav-article')) {
      item.style.display = (level >= 2) ? "block" : "none";
    } else if (classList.contains('nav-book')) {
      item.style.display = (level >= 1) ? "block" : "none";
    }
  }
  hidePopMenu();
}

//在导航栏定位到当前正在看的文章，此文章所在的书籍展开，如果文章不在屏幕范围为，则滚动直到可视
function locateCurrentArticle() {
  var art = g_currentArticle;
  if (isEmpty(art)) {
    return;
  }
  
  navExpandCollapseAll(0); //先全部折叠
  var navContent = document.getElementById('nav-content');
  var items = navContent.querySelectorAll('.nav-title');
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    if (item.getAttribute('data-src') == art.src) {
      var navArticle = item.parentElement;
      var navBook = navArticle.parentElement;
      var navItem = navBook.parentElement;
      var books = navItem.querySelectorAll('.nav-book'); //显示这一天所有的book
      for (var j = 0; j < books.length; j++) {
        books[j].style.display = "block";
      }
      navArticle.style.display = "block";
      navItem.style.display = "block";
      var icon = navItem.querySelector('.tree-icon');
      icon.innerHTML = "▾";
      scrollToNode(navContent, item);
      break;
    }
  }
}

//滚动容器，尽量让node位于容器可视范围中间位置
function scrollToNode(container, node) {
  var height = container.clientHeight;
  var nodeTop = node.offsetTop;
  var nodeHeight = node.clientHeight;
  var pos = Math.max(0, nodeTop - (height / 2) + (nodeHeight / 2));
  container.scrollTop = pos;
}

//高亮显示当前正在读的书
function highlightCurrentArticle() {
  var art = g_currentArticle;
  if (isEmpty(art)) {
    return;
  }
  
  var navContent = document.getElementById('nav-content');
  var items = navContent.querySelectorAll('.nav-title');
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    if (item.getAttribute('data-src') == art.src) {
      item.style.fontWeight = 'bold';
    } else {
      item.style.fontWeight = 'normal';
    }
  }
}

//删除一本或多本书
function navDeleteBooks(event) {
  hidePopMenu();
  if (isEmpty(g_books)) {
    return;
  }
  var chks = document.querySelectorAll('.nav-book-chk:checked');
  if (chks.length == 0) {
    alert(i18n.selectAtleastOneItem);
    return;
  }

  var books = [];
  var titles = []
  for (var i = 0; i < chks.length; i++) {
    books.push(chks[i].value); //bookDir
    titles.push(chks[i].nextElementSibling.textContent);
  }
  var titleStr = titles.slice(0, 5).join('\n');
  if (titles.length > 5) {
    titleStr += '\n...';
  }
  if (!(event.ctrlKey || event.metaKey) && !confirm(i18n.areYouSureDelete + '\n' + titleStr)) {
    return;
  }

  ajax_post('/reader/delete', {books: books.join('|')}, function (resp) {
    if (resp.status == 'ok') {
      deleteBooksAndUpdateUi(books);
    } else {
      alert(resp.status);
    }
  });
}

//删除本地数组中的元素然后更新页面，books为数组，元素为 'date/title'
function deleteBooksAndUpdateUi(books) {
  //[{date:, books: [{title:, articles:[{title:, src:}],},...]}, ]
  var removeSet = new Set(books);
  g_books = g_books.filter(function (entry) {
      entry.books = entry.books.filter(function (book) {
          return !removeSet.has(book.bookDir);
      });
      return entry.books.length > 0;
  });
  populateBooks(1);
}

//显示/隐藏导航设置菜单
function toggleNavPopMenu() {
  var menu = document.getElementById('nav-popmenu');
  var allowIcon = document.getElementById('allow-links').querySelector('.check-icon');
  allowIcon.innerHTML = g_allowLinks ? '✔' : '☐';
  var actIcon = document.getElementById('topleft-activate-dict').querySelector('.check-icon');
  actIcon.innerHTML = g_topleftDict ? '✔' : '☐';
  var darkIcon = document.getElementById('dark-mode').querySelector('.check-icon');
  darkIcon.innerHTML = g_darkMode ? '✔' : '☐';
  menu.style.display = (menu.style.display == 'block') ? 'none' : 'block';
  if (menu.style.display == 'none') {
    focusIframe(); //关闭菜单后把焦点还给文章
  }
}

//增加iframe的字号
function increaseFontSize() {
  g_fontSize = parseFloat(Math.min(g_fontSize * 1.2, 3.0).toFixed(1));
  adjustIFrameStyle();
  if (isMobile()) {
    hideNavbar();
  }
  saveSettings();
}

//减小iframe的字号
function decreaseFontSize() {
  g_fontSize = parseFloat(Math.max(g_fontSize * 0.8, 0.5).toFixed(1));
  adjustIFrameStyle();
  if (isMobile()) {
    hideNavbar();
  }
  saveSettings();
}

//将目前的配置保存到服务器
function saveSettings() {
  ajax_post('/reader/settings', {fontSize: g_fontSize, allowLinks: g_allowLinks, inkMode: g_inkMode,
    darkMode: g_darkMode, topleftDict: g_topleftDict});
}

//显示触摸区域图示
function showTouchHint() {
  hidePopMenu();
  if (isMobile()) {
    document.getElementById('navbar').style.display = 'none';
  }
  var iframe = document.getElementById('iframe');
  //iframe.style.height = 'auto'; //规避iframe只能变大不能变小的bug
  iframe.style.display = "none"; //加载完成后再显示
  iframe.src = '/reader/404?tips=';
}

//隐藏弹出的设置菜单
function hidePopMenu() {
  document.getElementById('nav-popmenu').style.display = 'none';
  focusIframe(); //菜单操作完把焦点还给文章，保证滚轮可用
}

//隐藏左侧导航栏
function hideNavbar() {
  hidePopMenu();
  if (isMobile()) {
    document.getElementById('navbar').style.display = 'none';
  }
}

//是否允许点击链接打开新网页
function toggleAllowLinks() {
  g_allowLinks = !g_allowLinks;
  var allowIcon = document.getElementById('allow-links').querySelector('.check-icon');
  allowIcon.innerHTML = g_allowLinks ? '✔' : '☐';
  saveSettings();
}

//切换左上角模式，默认为前一本书，可以切换为直接进入查词模式
function toggleTopleftDict() {
  g_topleftDict = !g_topleftDict;
  var actIcon = document.getElementById('topleft-activate-dict').querySelector('.check-icon');
  actIcon.innerHTML = g_topleftDict ? '✔' : '☐';
  saveSettings();
}

//切换黑暗模式
function toggleDarkMode() {
  g_darkMode = !g_darkMode;
  var darkIcon = document.getElementById('dark-mode').querySelector('.check-icon');
  darkIcon.innerHTML = g_darkMode ? '✔' : '☐';
  saveSettings();
  setDarkModeStyle();
}

//根据黑暗模式开关，设置当前界面的样式
function setDarkModeStyle() {
  var tag;
  if (g_darkMode) {
    //document.body.style.backgroundColor = '#121212';
    //document.body.style.color = '#e0e0e0';
    //tag = document.getElementById('corner-dict-hint');
    //tag.style.borderColor = '#ffffff transparent transparent transparent';
    //tag = document.getElementById('navbar');
    //tag.style.backgroundColor = '#121212';
    //tag.style.color = '#e0e0e0';
  } else {
    //tag = document.getElementById('corner-dict-hint')
    //tag.style.borderColor = '#291E1E transparent transparent transparent';
  }
  iframe.src = iframe.src; //强制刷新一次
}

//是否允许墨水屏模式
function toggleInkMode() {
  g_inkMode = !g_inkMode;
  setInkMode(g_inkMode);
  saveSettings();
}

//切换查词模式
function toggleDictMode() {
  g_dictMode = !g_dictMode;
  document.getElementById('tr-result').style.display = 'none';
  document.getElementById('corner-dict-hint').style.display = g_dictMode ? 'block' : 'none';
  hideNavbar();
}

//根据是否使能墨水屏模式，设置相应的元素属性
function setInkMode(enable) {
  return; //暂时先禁用
  var container = document.getElementById('container');
  var content = document.getElementById('content');
  var indicator = document.getElementById('pos-indicator');
  var icon = document.getElementById('ink-mode').querySelector('.check-icon');
  var body = document.body;
  if (enable) {
    icon.innerHTML = '✔';
    container.style.height = getViewportHeight() + 'px';
    content.style.height = getViewportHeight() + 'px';
    content.style.scrollbarWidth = "none";
    //body.style.overflow = 'hidden';
    //body.style.scrollbarWidth = 'none';
    //body.style.scrollbarColor = 'transparent';
    //body.style.msOverflowStyle = 'none';
    //indicator.style.display = 'block';
  } else {
    icon.innerHTML = '☐';
    container.style.height = g_iframeScrollHeight + 'px';
    content.style.height = g_iframeScrollHeight + 'px';
    content.style.scrollbarWidth = "auto";
    //body.style.overflow = 'auto';
    //body.style.scrollbarWidth = 'auto';
    //body.style.scrollbarColor = 'auto';
    //body.style.msOverflowStyle = 'scrollbar';
    //indicator.style.display = 'none';
  }
}

//根据当前的文章列表，填充左侧导航栏
//expandLevel：控制初始显示的内容, 0-全部折叠，1-仅显示日期和书名，2-显示全部内容
function populateBooks(expandLevel) {
  var navContent = document.getElementById('nav-content');
  var ostr = [];
  for (var i = 0; i < g_books.length; i++) {
    var someDay = g_books[i];
    var dateStr = someDay.date;
    var books = someDay.books;
    if (!dateStr || !books || books.length == 0) {
      continue;
    }

    ostr.push('<div class="nav-item">' +
                '<div class="nav-date">' +
                  '<span class="tree-icon">&#x25b8;</span>');
    ostr.push(    '<span>' + dateStr + '</span>');
    ostr.push(  '</div>');
    for (var bIdx = 0; bIdx < books.length; bIdx++) {
      var book = books[bIdx];
      var articles = book.articles;
      if (!book || !articles || articles.length == 0) {
        continue;
      }
      ostr.push(
        '<div class="nav-book">' +
          '<div class="nav-book-title">' +
            '<input type="checkbox" class="nav-book-chk" onclick="javascript:event.stopPropagation();focusIframe()" value="' + book.bookDir + '"/>');
      ostr.push('<span>' + book.title + '</span>');
      ostr.push(
          '</div>');
      ostr.push(
          '<div class="nav-article">');
      for (var aIdx = 0; aIdx < articles.length; aIdx++) {
        var article = articles[aIdx];
        if (!article || !article.src || !article.title) {
          continue;
        }
        var sTitle = article.title.replace(/"/g, '&quot;');
        ostr.push(
             '<div class="nav-title" data-src="' + article.src +'">' +
                '<div>' +
                  articleSvgIcon() +
                  '<span class="nav-title-text" title="' + sTitle + '">' + article.title + '</span>' +
                '</div>' +
              '</div>');
      }
      ostr.push(
          '</div>');
      ostr.push(
        '</div>');
    }
    ostr.push('</div>');
  }

  if (ostr.length > 0) {
    navContent.innerHTML = ostr.join('');
    navExpandCollapseAll(expandLevel);
  } else {
    //使用一个svg图像代替
    var svgDiv = document.getElementById('nothing-here');
    navContent.innerHTML = svgDiv.innerHTML;
  }
}

//文章前面的svg图标
function articleSvgIcon() {
  return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 11a9 9 0 0 1 9 9"></path><path d="M4 4a16 16 0 0 1 16 16"></path><circle cx="5" cy="19" r="1"></circle></svg>';
}

//判断点击的节点或父节点有没有包含特定的类名
function nodeOrChild(klass, target, parent) {
  while (target && target != parent) {
    if (target.classList.contains(klass)) {
      return target;
    }
    target = target.parentElement;
  }
  return null;
}

//监听点击文章标题的事件，展开或折叠树形结构，打开点击的文章
//此事件注册在nav-content上
function navClickEvent(event) {
  var parent = document.getElementById('nav-content');
  var target = event.target || event.srcElement;
  
  var navDate = nodeOrChild('nav-date', target, parent);
  var navBook = nodeOrChild('nav-book', target, parent);
  var navTitle = nodeOrChild('nav-title', target, parent);
  if (navTitle) {
    var src = navTitle.getAttribute('data-src');
    var span = navTitle.querySelector('.nav-title-text');
    var title = span ? span.textContent.trim() : '';
    if (src && title) {
      openArticle({title: title, src: src});
    }
  } else if (navBook) {
    toggleNavBook(navBook);
  } else if (navDate) {
    toggleNavDate(navDate);
  } else {
    focusIframe(); //点击导航栏空白处也把焦点还给文章
  }
}

//推送当前正在阅读的书籍
function pushCurrentBook() {
  var art = g_currentArticle;
  if (!isEmpty(art)) {
    ajax_post('/reader/push', {type: 'book', src: art.src, title: art.title}, function (resp) {
      if (resp.status == 'ok') {
        alert(i18n.pushOk + '\n' + art.title);
      } else {
        alert(resp.status);
      }
    });
  } else {
    alert(i18n.noReading);
  }
  hidePopMenu();
}

//推送当前正在阅读的文章
function pushCurrentArticle() {
  var art = g_currentArticle;
  if (!isEmpty(art)) {
    var language = getBookLanguage(art);
    ajax_post('/reader/push', {type: 'article', src: art.src, title: art.title, language: language}, 
      function (resp) {
        if (resp.status == 'ok') {
          alert(i18n.pushOk + '\n' + art.title);
        } else {
          alert(resp.status);
        }
    });
  } else {
    alert(i18n.noReading);
  }
  hidePopMenu();
}

//通过一个文章获取对应书本的语言，在调用时请保证art合法
function getBookLanguage(art) {
  for (var i = 0; i < g_books.length; i++) {
    var entry = g_books[i]; //date
    for (var j = 0; j < entry.books.length; j++) {
      var book = entry.books[j];
      var articles = book.articles;
      for (var k = 0; k < articles.length; k++) {
        if (articles[k].src == art.src) {
          return book.language;
        }
      }
    }
  }
  return '';
}

//点击某篇文章后在iframe打开，article是字典
function openArticle(article) {
  if (article.src) {
    var iframe = document.getElementById('iframe');
    var oldSrc = g_currentArticle.src ? g_currentArticle.src.replace(/#.*$/, '') : '';
    var newSrc = article.src.replace(/#.*$/, '');
    if (oldSrc != newSrc) {
      iframe.style.display = "none"; //加载完成后再显示
    }
    iframe.src = '/reader/article/' + article.src;
    g_currentArticle = article;
  }
  hideNavbar();
  closeDictDialog();
  highlightCurrentArticle();
}

//打开上一篇文章
function openPrevArticle() {
  openArticle(findPreviousArticle(g_currentArticle));
  locateCurrentArticle();
}

//打开下一篇文章
function openNextArticle() {
  openArticle(findNextArticle(g_currentArticle));
  locateCurrentArticle();
}

//给定一篇文章，返回此文章前一篇文章，如果art为空，则返回第一篇文章
//返回为一个字典对象
function findPreviousArticle(art) {
  var prev = {};
  for (var i = 0; i < g_books.length; i++) {
    var entry = g_books[i]; //date
    for (var j = 0; j < entry.books.length; j++) {
      var book = entry.books[j];
      var articles = book.articles;
      for (var k = 0; k < articles.length; k++) {
        var current = articles[k];
        if (!art.src) {
          return current;
        } else if (current.src == art.src) {
          return prev;
        }
        prev = current;
      }
    }
  }
  return prev;
}

//给定一篇文章，返回此文章后一篇文章，如果art为空，则返回第一篇找到的文章
//返回为一个字典 {title:, src:,}
function findNextArticle(art) {
  var found = false;
  for (var i = 0; i < g_books.length; i++) {
    var entry = g_books[i]; //date
    for (var j = 0; j < entry.books.length; j++) {
      var book = entry.books[j];
      var articles = book.articles;
      for (var k = 0; k < articles.length; k++) {
        var current = articles[k];
        if (found || !art.src) {
          return current;
        }
        if (current.src == art.src) {
          found = true;
        }
      }
    }
  }
  return {};
}

//iframe每次加载一个新的文档后会调用此函数，注册一些事件并更新一些变量
function iframeLoadEvent(evt) {
  var iframe = document.getElementById('iframe');
  var doc = iframe.contentDocument || iframe.contentWindow.document;

  //决定滚动方案：窄屏/触屏/墨水屏设备/此前探测失败者使用旧方案
  g_legacyScroll = shouldUseLegacyScroll();
  if (!g_legacyScroll) {
    //先按新方案布局(fix高度后文档才有滚动范围)，再做一次滚动能力探测，
    //不支持iframe内部滚动的浏览器整个会话回退旧方案，避免翻页失效
    iframe.style.display = "block";
    iframe.style.height = (getViewportHeight() + 40) + 'px';
    if (!g_innerScrollVerified && (iframeScrollHeight(doc) > iframeClientHeight(doc) + 4)) {
      if (innerScrollWorks(doc)) {
        g_innerScrollVerified = true;
      } else {
        g_innerScrollBroken = true;
        g_legacyScroll = true;
      }
    }
  }

  adjustIFrameStyle(iframe);

  //方案可能中途改变(如探测失败回退)，同步外层容器的滚动属性和iframe高度
  adjustContentHeight();

  if (g_legacyScroll) {
    //外层滚动方案需要持续测量内容高度，监听内容变化
    if (window.MutationObserver) {
      var observer = new MutationObserver(function(mutations) {
        recalculateHeight(iframe, doc);
      });

      observer.observe(doc.body, {
        childList: true,
        subtree: true,
        attributes: true,
        characterData: true
      });
    }
  } else {
    //iframe内部滚动方案，进度指示器跟随内层滚动更新
    doc.addEventListener('scroll', updatePosIndicator);
    updatePosIndicator();
    focusIframe(); //确保文章加载后滚轮/键盘直接作用于文章
  }

  doc.addEventListener('click', function(event) {
    //处理链接的点击事件
    var target = event.target || event.srcElement;
    if (target && (target.tagName == 'A')) {
      event.stopPropagation();
      event.preventDefault();
      var href = target.getAttribute('href');
      if (href && g_allowLinks) {
        openLinkInNewTab(href);
        return;
      }
    }

    //判断是否查词典
    var selection = doc.getSelection();
    var text = selection.toString();
    var dictDialog = document.getElementById('tr-result');
    if (g_dictMode) {
      text = text || getWordAtClick(event, iframe);
      if (text) {
        translateWord(text, selection);
      }
      g_dictMode = false;
      document.getElementById('corner-dict-hint').style.display = 'none';
    } else if (dictDialog && dictDialog.style.display == 'block') { //关闭查词窗口
      closeDictDialog();
    } else if (!text) { //没有选择文本才翻页
      clickEvent(event);
    }
  });

  //只有PC有键盘快捷键
  if (!isMobile()) {
    doc.addEventListener('keydown', documentKeyDownEvent);
  }
}

//每次iframe加载完成后调整其样式和容器高度
function adjustIFrameStyle(iframe) {
  iframe = iframe || document.getElementById('iframe');
  var doc = iframe.contentWindow.document || iframe.contentDocument;
  var body = doc.body;
  iframe.style.display = "block";
  if (g_legacyScroll) {
    //外层滚动方案(旧方案)：iframe高度等于内容高度，必须测量，
    //保留spacer规避chrome对iframe高度计算不准确的问题
    iframe.style.height = '999999px';
    if (!doc.getElementById('ke-height-spacer')) {
      var spacer = doc.createElement('div');
      spacer.id = 'ke-height-spacer';
      spacer.innerHTML = '<div style="clear:both;"></div><br/><p>■ END</p><br/><br/>';
      body.appendChild(spacer);
    }
    body.offsetHeight; //强制重排
    iframe.style.height = 'auto';
    //禁止iframe文档内部滚动(等效于原来的scrolling="no"，
    //iframe高度含冗余量时避免出现内部滚动条，与旧行为一致。
    //webshelf文章无DOCTYPE以quirks模式渲染，滚动元素是body，两处都设置)
    doc.documentElement.style.overflow = 'hidden';
    body.style.overflow = 'hidden';
    //个别内核对scrolling=auto的iframe恒画滚动条槽，旧方案恢复为no
    iframe.setAttribute('scrolling', 'no');
  } else {
    //iframe内部滚动方案(新方案)：高度固定为视口高度加40px冗余(与旧方案一致)，
    //短页面(如404提示页)不会因注入的边距恰好溢出几像素而显示滚动条；
    //多出的40px被#content(overflow:hidden)裁掉不可见，
    //长文章的滚动条即阅读滚动条，翻页步长=iframe视口高-40=页面可视高度
    iframe.style.height = (getViewportHeight() + 40) + 'px';
    doc.documentElement.style.scrollBehavior = 'auto'; //翻页瞬时跳转，旧浏览器会忽略此属性
    iframe.setAttribute('scrolling', 'auto');
  }

  body.style.textAlign = 'justify';
  body.style.wordWrap = 'break-word';
  body.style.hyphens = 'auto';
  //404提示页是随视口伸缩的全屏布局(html,body{height:100%})，注入边距会使文档
  //恰好超出视口几像素而在新方案下显示滚动条，该页自带完整样式，跳过边距注入
  var isNotFoundPage = (doc.location.pathname.indexOf('/reader/404') === 0);
  if (isNotFoundPage && !g_legacyScroll) {
    body.style.margin = '0px';
    body.style.paddingBottom = '0px';
  } else {
    body.style.margin = '10px 20px 10px 20px';
    body.style.paddingBottom = '20px';
    //外层滚动方案下iframe被加宽20px并裁剪(见adjustContentHeight)，
    //加大右边距避免文字流进被裁剪的右侧20px区域
    if (g_legacyScroll && (isMobile() || isEinkBrowser())) {
      body.style.marginRight = '40px';
    }
  }
  body.style.fontSize = g_fontSize.toFixed(1) + 'em';
  body.style.cursor = 'pointer';
  body.style.webkitTapHighlightColor = 'transparent';
  body.style.webkitTouchCallout = 'none';

  if (g_darkMode) { //黑暗模式
    body.style.backgroundColor = '#121212';
    body.style.color = '#e0e0e0';
    var links = doc.querySelectorAll('a');
    for (var i = 0; i < links.length; i++) {
      links[i].style.color = '#bb86fc';
    }
  } else {
    //注释以下代码，使用默认值
    //body.style.backgroundColor = '#ffffff';
    //body.style.color = '#000000';
    //var links = doc.querySelectorAll('a');
    //for (var i = 0; i < links.length; i++) {
    //  links[i].style.color = '#1a0dab';
    //}
  }

  var images = doc.querySelectorAll('img');
  for (var i = 0; i < images.length; i++) {
    var img = images[i];
    img.style.maxWidth = '100%';
    img.style.height = 'auto';
    // 图片加载完成后重新计算高度，仅外层滚动方案需要
    if (g_legacyScroll && !img.complete) {
      img.addEventListener('load', function() {
        recalculateHeight(iframe, doc);
      });
    }
  }

  if (g_legacyScroll) {
    recalculateHeight(iframe, doc);
  }
}

//计算iframe最终高度(仅外层滚动方案使用，新方案iframe高度固定不需要测量)
function recalculateHeight(iframe, doc) {
  var body = doc.body;
  var html = doc.documentElement;
  var vh = getViewportHeight();
  
  // 获取所有内容元素的高度
  //var allElements = body.getElementsByTagName('*');
  //var maxHeight = 0;
  //for (var i = 0; i < allElements.length; i++) {
  //  var elem = allElements[i];
  //  var bottom = elem.offsetTop + elem.offsetHeight;
  //  maxHeight = Math.max(maxHeight, bottom);
  //}

  // 获取spacer元素的位置
  var spacer = doc.getElementById('ke-height-spacer');
  var spacerBottom = spacer ? (spacer.offsetTop + spacer.offsetHeight) : 0;
  
  var height = Math.max(
    spacerBottom,
    body.scrollHeight,
    body.offsetHeight,
    html.scrollHeight,
    html.offsetHeight,
    vh
  );
  height += 40;
  iframe.style.height = height + 'px';
  g_iframeScrollHeight = height;
}

//使用键盘快捷键翻页
function documentKeyDownEvent(event) {
  var key = event.key;
  //console.log('Key pressed:', key);
  if ((key == ' ') || (key == 'ArrowRight') || (key == 'PageDown')) {
    event.stopPropagation();
    event.preventDefault();
    pageDown();
  } else if (key == 'ArrowDown') {
    event.stopPropagation();
    event.preventDefault();
    openNextArticle();
  } else if ((key == 'ArrowLeft') || (key == 'PageUp')) {
    event.stopPropagation();
    event.preventDefault();
    pageUp();
  } else if (key == 'ArrowUp') {
    event.stopPropagation();
    event.preventDefault();
    openPrevArticle();
  }
}

//文档加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
  var content = document.getElementById('content');
  var navContent = document.getElementById('nav-content');
  var iframe = document.getElementById('iframe');
  adjustContentHeight();
  initNavResizer();
  window.addEventListener('resize', function () {
    g_pageHeight = 0; //窗口尺寸变化后重新校准
    g_heightCalibrated = false;
    adjustContentHeight();
  });
  document.addEventListener('keydown', documentKeyDownEvent);
  //window.addEventListener('message', iFrameEvent);
  content.addEventListener('click', clickEvent);
  content.addEventListener('scroll', updatePosIndicator);
  navContent.addEventListener('click', navClickEvent);
  navContent.addEventListener('scroll', updateNavIndicator);
  iframe.addEventListener('load', iframeLoadEvent);
  populateBooks(1);
  iframe.style.display = "none"; //加载完成后再显示
  //个别内核对scrolling=auto的iframe恒画滚动条槽，旧方案在重载前恢复为no使其生效
  iframe.setAttribute('scrolling', g_legacyScroll ? 'no' : 'auto');
  iframe.src = iframe.src; //强制刷新一次，避免偶尔出现不能点击的情况
  setDarkModeStyle();
});
