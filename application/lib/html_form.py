#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#兼容mechanize接口而定制的一个简单的Html form类

class ControlNotFoundError(Exception):
    pass

#提供mechanize类似的基本接口
class HTMLForm:
    #tag为BeautifulSoup的form的tag对象
    def __init__(self, form):
        self.form = form
        self._data = {}
    
    #获取表单的属性，比如action等
    def get(self, attr, default=None):
        return self.form.get(attr, default)

    #设置表单内对应 name 控件的 value值
    def __setitem__(self, name, value):
        ctl = self.find_control(name=name)
        if ctl:
            ctl['value'] = value
        
    def set_all_readonly(self, x):
        pass

    def find_control(self, name=None, type=None, kind=None, id=None, predicate=None, nr=None, label=None):
        tagName = None
        attrs = {}
        if name:
            attrs['name'] = name
        if type:
            attrs['type'] = type
        if kind == 'clickable':
            attrs['type'] = 'submit'
        elif kind == 'input':
            tagName = 'input'
        elif kind == 'text': #INPUT/TEXT, INPUT/PASSWORD, INPUT/HIDDEN, TEXTAREA
            tagName = 'input'
            attrs['type'] = lambda x: x['type'] in ['text', 'password', 'hidden', 'textarea']
        if id:
            attrs['id'] = id

        if tagName:
            controls = self.form.find_all(tagName, attrs=attrs) if attrs else self.form.find_all(tagName)
        else:
            controls = self.form.find_all(attrs=attrs) if attrs else self.form.find_all()
        controls = list(controls)

        if nr and nr < len(controls):
            return controls[nr]
        elif predicate:
            controls = list(filter(predicate, controls))
            if controls:
                return controls[0]
        elif controls:
            return controls[0]
        
        return None

    #获取表单内所有控件的name/value属性字典
    def get_all_values(self):
        ret = {}
        for tag in self.form.find_all(attrs={'name':True}):
            name = tag.get('name')
            value = None
            if tag.name == 'input':
                value = tag.get('value')
            elif tag.name == 'select':
                opt = tag.find('option', selected=True)
                value = opt.get('value') if opt else None
            if value is not None:
                ret[name] = value
        return ret

    #选择input的value
    def set_input(self, name, value):
        input_ = self.form.find("input", {"name": name})
        if input_:
            input_["value"] = value

    #设置多选框的选择状态
    def set_checkbox(self, name, value):
        tag = self.form.find('input', attrs={'type': 'checkbox', 'name': name})
        if tag:
            if value:
                tag['checked'] = ''
            elif 'checked' in tag.attrs:
                del tag.attrs['checked']

    #设置单选框的选择状态
    def set_radio(self, name, value):
        tags = self.form.find_all('input', attrs={'type': 'radio', 'name': name})
        if tags:
            self.uncheck_all(name)
            for radio in tags:
                if radio.get("value", "on") == str(value):
                    radio["checked"] = ""
                    break

    #取消所有同样名字的单选多多选的选择状态
    def uncheck_all(self, name):
        for tag in self.form.find_all("input", {"name": name}):
            if "checked" in tag.attrs:
                del tag.attrs["checked"]

    #设置TextArea的文本
    def set_textarea(self, name, txt):
        tag = self.form.find("textarea", {"name": name})
        if tag:
            tag.string = txt

    #下拉框选择一个数值
    def set_select(self, name, value):
        select = self.form.find("select", {"name": name})
        if not select:
            return

        for option in select.find_all("option"):
            if "selected" in option.attrs:
                del option.attrs["selected"]

        option = select.find("option", {"value": value})
        if not option:
            option = select.find("option", string=value)
        if option:
            option.attrs["selected"] = "selected"
