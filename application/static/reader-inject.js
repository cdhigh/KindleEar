//文档加载完成
document.addEventListener('DOMContentLoaded', function() {
  var clientHeight = window.innerHeight || document.documentElement.clientHeight;
  var scrollHeight = document.documentElement.scrollHeight || document.body.scrollHeight;
  var data  = {type: 'iframeLoaded', clientHeight: clientHeight, scrollHeight: scrollHeight};
  window.parent.postMessage(data, "*");
  document.addEventListener('click', function (event) {
    var eventDict = clickEventToDict(event);
    var data  = {type: 'click', event: eventDict, href: '', clientHeight: clientHeight, scrollHeight: scrollHeight};
    window.parent.postMessage(data, "*");
  });
  setupLinkListener(clientHeight, scrollHeight);
});

//将点击事件转换为字典，用于不同frame之间的消息传递
function clickEventToDict(event) {
  return {
    type: event.type,
    //target: event.target.tagName,
    //currentTarget: event.currentTarget.tagName,
    //eventPhase: event.eventPhase,
    //bubbles: event.bubbles,
    //cancelable: event.cancelable,
    //defaultPrevented: event.defaultPrevented,
    //isTrusted: event.isTrusted,
    //timestamp: event.timeStamp,
    altKey: event.altKey,
    ctrlKey: event.ctrlKey,
    metaKey: event.metaKey,
    shiftKey: event.shiftKey,
    button: event.button,
    buttons: event.buttons,
    clientX: event.clientX,
    clientY: event.clientY,
    pageX: event.pageX,
    pageY: event.pageY,
    screenX: event.screenX,
    screenY: event.screenY,
    offsetX: event.offsetX,
    offsetY: event.offsetY,
    movementX: event.movementX,
    movementY: event.movementY
  };
}

//点击iframe内部的链接后给父容器发送消息，让父容器决定是否打开链接并处理前进后退逻辑
function setupLinkListener(clientHeight, scrollHeight) {
  var links = document.querySelectorAll('a');
  for (var i = 0; i < links.length; i++) {
    links[i].addEventListener('click', function(event) {
      event.stopPropagation();
      event.preventDefault();
      var href = event.target.getAttribute('href');
      var eventDict = clickEventToDict(event);
      var data = {type: 'click', href: href, event: eventDict, clientHeight: clientHeight, scrollHeight: scrollHeight};
      window.parent.postMessage(data, '*');
    });
  }
}
