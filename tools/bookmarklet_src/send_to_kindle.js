//bookmarklet source code for "Send to Kindle"
//convert to bookmarklet by using <https://chriszarate.github.io/bookmarkleter>
//or <https://www.yourjs.com/bookmarklet>
//如果不需要html标签信息，可以使用：var s = window.getSelection().toString();
var o={userName:"{{user.name}}", key:"{{share_key}}", title:document.title, urls:window.location.href};
var s=window.getSelection().rangeCount?(new XMLSerializer()).serializeToString(window.getSelection().getRangeAt(0).cloneContents()):'';
if(s){
  o["text"]=s;
  (function(url, formData){
    var h = (tag, props)=>Object.assign(document.createElement(tag), props);
    var form = h("form", {action:url, method:"post", hidden:true, target:"_blank"});
    for (var [name, value] of Object.entries(formData)){
      form.appendChild(h("input", {name: value}));
    }
    document.body.appendChild(form);
    form.submit();
    setTimeout(()=>{form.remove();},100);
    alert("The text you selected ("+s.length()+"Bytes) has been sent to KindleEar.");
  })("{{url2book_url}}", o);
}else{
  open("{{url2book_url}}?"+(new URLSearchParams(o)).toString());
}
