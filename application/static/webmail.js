var g_prevPreviewId = false;

//从一个包含查询字符串的url里面提取某个查询参数，不存在返回空串
function GetUrlQueryParam(url, key) {
  let params = '', value = '';
  try {
    params = new URLSearchParams(new URL(url).search);
    value = params.get(key);
  } catch (e) {console.log(e);}
  return value ? decodeURIComponent(value) : '';
}

//从服务器获取邮件列表
//如果网页链接里面有查询字符串 includes=all ，则包含已经被标识为删除的邮件
function FetchMailList() {
  let includes = GetUrlQueryParam(window.location.href, 'includes');
  let url = (includes == 'all') ? '/webmail/list?includes=all' : '/webmail/list';
  MakeAjaxRequest(url, "GET", null, function (resp) {
    all_mails = resp.data;
    PopulateMailList(all_mails);
  });
}

//使用字典列表填充网页的邮件列表
function PopulateMailList(mails) {
  g_prevPreviewId = false;
  $('#toggle_select_mail').prop('checked', false);
  const $tbody = $('.mail-list-table tbody');
  $tbody.empty();
  if (mails && mails.length > 0) {
    $.each(mails, function(index, mail) {
      let size = ReadableFileSize(mail.size);
      const row = `<tr data-index="${index}" class="${mail.status}">
                    <td><input type="checkbox" class="mail_checkbox"></td>
                    <td>${mail.sender}</td>
                    <td>${mail.to}</td>
                    <td>${mail.subject}</td>
                    <td>${mail.datetime}</td>
                    <td>${size}</td>
                  </tr>`;
      $tbody.append(row);
    });
  } else {
    $tbody.append('<tr><td colspan="6" style="text-align:center;">{0}</td></tr>'.format(i18n.nothingHere));
  }
}

//显示邮件预览
//index: all_mails列表的索引号
function DisplayMailPreview(index) {
  const mail = all_mails[index];
  const mailId = mail.id;
  if (mailId === g_prevPreviewId) {
    return;
  }

  const $mailPreview = $('#mailPreview');
  $mailPreview.html('');
  if (!mail) {
    return;
  }
  MakeAjaxRequest(`/webmail/content/${mailId}`, "GET", null, function (resp) {
    let content = `<div class="mail-preview-header"><h4>${mail.subject}</h4>
                  <strong>${i18n.from}:</strong> ${mail.sender}<br/>
                  <strong>${i18n.to}:</strong> ${mail.to}<br/>
                  <strong>${i18n.time}:</strong> ${mail.datetime}<br/></div>
                  <div class="mail-preview-content">${resp.content}</div>`;
    $mailPreview.html(content);
    g_prevPreviewId = mailId;
  });
}

//切换已读/未读状态按钮
function ToggleMailReadStatus() {
  const selectedMails = GetSelectedMails();
  if (selectedMails.length > 0) {
    selectedMails.forEach(item => {
      let orgStatus = item.mail.status;
      if (orgStatus != 'deleted') {
        let status = (orgStatus == 'unread') ? 'read' : 'unread';
        SetMailStatus(item.index, status);
      }
    });
  } else {
    alert(i18n.selectAtleastOneMail);
  }
}

//设置某个邮件已读状态
function SetMailStatus(index, status) {
  const mail = all_mails[index];
  if (mail && (mail.status != 'deleted') && (mail.status !== status)) {
    MakeAjaxRequest('/webmail/status', "POST", {id: mail.id, status: status}, function (data) {
      var $row = $('tr[data-index="' + index + '"]');
      $row.removeClass(mail.status).addClass(status);
      mail.status = status;
    });
  }
}

//点击的邮件行设置高亮状态
function HighlightMail(index) {
  return; //高亮状态和左侧的checkbox有时候会引起混淆，先屏蔽此功能
  $('tr').each(function() {
    let $tr = $(this);
    const idx = $tr.data('index');
    if (idx == index) {
      $tr.addClass('highlighted');
    } else {
      $tr.removeClass('highlighted');
    }
  });
}

//获取当前选择的所有邮件行
function GetSelectedMails() {
  const selectedMails = [];
  $('.mail_checkbox:checked').each(function() {
    const index = $(this).closest('tr').data('index');
    const mail = all_mails[index];
    if (mail) {
      selectedMails.push({index: index, mail: mail});
    }
  });
  return selectedMails;
}

//点击一个邮件行，预览邮件内容
function ClickOnMailRow() {
  const index = $(this).data('index');
  SetMailStatus(index, 'read');
  HighlightMail(index);
  DisplayMailPreview(index);
}

//选择全部或取消选择全部
function SelectUnselectMails() {
  if ($('#toggle_select_mail').prop('checked')) {
    $('.mail_checkbox:not(:checked)').each(function () {
      $(this).prop('checked', true);
    });
  } else {
    $('.mail_checkbox:checked').each(function () {
      $(this).prop('checked', false);
    });
  }
}

//回复或转发邮件
//sender: KindleEar的发件人地址
//act: 'reply'-回复，'forward'-转发
function ReplyMail(sender, act) {
  const selectedMails = GetSelectedMails();
  if (selectedMails.length != 1) {
    alert(i18n.selectSingleMail);
    return;
  }

  let mail = selectedMails[0].mail;
  let to = (act == 'reply') ? mail.sender : '';
  let subject = ((act == 'reply') ? 'Re: ' : 'Fw: ') + mail.subject;
  let textarea = ``;
  let attachSymbol = (act == 'attachment') ? '&#128206; attachment.html' : '';
  MakeAjaxRequest("/webmail/content/" + mail.id, "GET", null, function (resp) {
    let content = (act != 'attachment') ? ('<br/><br/><hr/>' + resp.content) : '';
    let ostr = `<div class="reply-container">
        <div class="reply-header">${i18n.from}:</div>
        <div class="reply-header">${sender}</div>
        <div class="reply-header">${i18n.to}:</div>
        <div class="reply-header"><input type="email" id="reply_to" value="${to}" /></div>
        <div class="reply-header">${i18n.subject}:</div>
        <div class="reply-header"><input type="text" id="reply_subject" value="${subject}" /></div>
        <div class="reply-content"><div id="reply_textarea" contenteditable="true" class="textarea" autofocus>${content}</div>
        <span style="cursor:pointer" onclick="SaveMail('${mail.id}')">${attachSymbol}</span></div>`;
    let buttons = [[i18n.send, 'actionButton act h5-dialog-ok'], [i18n.cancel, 'actionButton h5-dialog-cancel']];
    showH5Dialog(ostr, buttons).then(function (idx) {
      let to = $('#reply_to').val();
      let subject = $('#reply_subject').val();
      let $replyDiv = $('#reply_textarea');
      let content = $replyDiv.html();
      let text = $replyDiv.text();
      if (!to || !subject || !content || !text) {
        alert(i18n.someParamsMissing);
      } else {
        let data = {to: to, subject: subject, content: content, text: text};
        if (act == 'attachment') {
          data['attachment'] = resp.content;
          data['attach_name'] = 'attachment.html';
        }
        MakeAjaxRequest("/webmail/send", "POST", data, function (resp) {
          ShowSimpleModalDialog('<p>{0}</p>'.format(i18n.mailBeenSent));
        });
      }
    }).catch(function(){});
  });
}

//删除/取消删除一个或多个邮件
function DeleteMails(act) {
  const selectedMails = GetSelectedMails();
  if (selectedMails.length > 0) {
    if (!confirm(i18n.areYouSureDelete.format(`${selectedMails.length} mails`))) {
      return;
    }

    $('#toggle_select_mail').prop('checked', false);

    let ids = selectedMails.map(item=>item.mail.id);
    let isUndelete = selectedMails.every(item=>item.mail.status=='deleted');
    let url = isUndelete ? "/webmail/undelete" : "/webmail/delete";
    MakeAjaxRequest(url, "POST", {ids: ids.join(',')}, function (resp) {
      if (isUndelete) { //取消删除
        selectedMails.forEach(item => {
          item.mail.status = 'read';
        });
      } else {
        //需要倒序遍历以避免索引问题
        selectedMails.reverse().forEach(item => {
          all_mails.splice(item.index, 1);
        });
      }
      PopulateMailList(all_mails);
    });
  } else {
    alert(i18n.selectAtleastOneMail);
  }
}

//将一个邮件的内容保存到本地
function SaveMail(id) {
  MakeAjaxRequest("/webmail/content/" + id, "GET", null, function (resp) {
    let $tag = $('<a>', {
      href: "data:text/plain;charset=UTF-8," + encodeURIComponent(resp.content),
      download: 'attachment.html',
      style: 'display:none;'
    });
    $('body').append($tag);
    $tag[0].click();
    $tag.remove();
  });
}
