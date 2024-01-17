#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Author: cdhigh<https://github.com/cdhigh>
import os, uuid

#模拟文件系统目录树结构的一个字典类
#file_system = FileSystemDict()
#file_system['dir1/dir2/file4.txt'] = 'content'
#print(file_system['dir1/dir2/file4.txt'])
class FileSystemDict(dict):
    def __getitem__(self, key_path):
        keys = key_path.replace('\\', '/').strip('/').split('/')
        current = self
        for key in keys:
            current = dict.__getitem__(current, key)
        return current

    def __setitem__(self, key_path, value):
        keys = key_path.replace('\\', '/').strip('/').split('/')
        current = self
        for key in keys[:-1]:
            if key not in current:
                dict.__setitem__(current, key, {})
            current = current[key]
        dict.__setitem__(current, keys[-1], value)
        
    #判断一个路径或文件是否存在
    def exists(self, key_path):
        keys = key_path.replace('\\', '/').strip('/').split('/')
        current = self

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        return True

    #判断是否是目录并且是否存在
    def isdir(self, key_path):
        keys = key_path.replace('\\', '/').strip('/').split('/')
        current = self

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        return isinstance(current, dict)

    #遍历，返回 (path, filecontent)
    def traverse(self, current_node=None, current_path='', iter_only_key=False):
        if current_node is None:
            current_node = self

        for key, value in current_node.items():
            path = f"{current_path}/{key}" if current_path else key

            if isinstance(value, dict):
                yield from self.traverse(value, path, iter_only_key)
            else:
                yield path if iter_only_key else (path, value)

    #遍历，返回 文件名，不返回目录名
    def __iter__(self):
        return iter(self.traverse(iter_only_key=True))

    #改名，类似linux的mv命令，可以改名，也可以移动文件
    def rename(self, old_path, new_path):
        old_keys = old_path.replace('\\', '/').strip('/').split('/')
        new_keys = new_path.replace('\\', '/').strip('/').split('/')

        #获取旧路径的最后一个键（文件或目录名）
        old_name = old_keys[-1]
        new_name = new_keys[-1]
        old_parent_path = '/'.join(old_keys[:-1]) if len(old_keys) > 1 else ''
        new_parent_path = '/'.join(new_keys[:-1]) if len(new_keys) > 1 else ''

        #获取旧路径的值
        current = self
        for key in old_keys[:-1]:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                raise ValueError(f"Cannot move path '{old_path}', it does not exist.")

        if isinstance(current, dict) and old_name in current:
            value = current.pop(old_name) #获取旧路径的值，并从字典中删除

            new_parent = self #获取新路径的父目录
            for key in new_keys[:-1]:
                if isinstance(new_parent, dict) and key in new_parent:
                    new_parent = new_parent[key]
                else:
                    new_parent[key] = {}  #如果新路径中的目录不存在，创建之
                    new_parent = new_parent[key]
            new_parent[new_name] = value
        else:
            raise ValueError(f"Cannot move path '{old_path}', it does not exist.")

    #删除一个文件或目录树，同时返回被删除的文件或目录内容
    def delete(self, path):
        keys = path.replace('\\', '/').strip('/').split('/')
        name = keys[-1]
        
        current = self
        for key in keys[:-1]:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                raise ValueError(f"Cannot delete '{path}', it does not exist.")

        if isinstance(current, dict) and name in current:
            return current.pop(name)
        else:
            raise ValueError(f"Cannot delete '{path}', it does not exist.")



    #创建一个临时文件
    @classmethod
    def make_tempfile(self, suffix="", prefix="", dir_='', mode='w+b'):
        return '{}{}{}'.format(prefix, uuid.uuid4(), suffix)

    def __bool__(self):
        return True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


#提供给OEB的文件读写桩
class FsDictContainer(object):
    def __init__(self, path, log, ignore_opf=False):
        self.fs_dict = path
        self.log = log if log else default_log
        self.opfname = None
        if not ignore_opf:
            for path in self.namelist():
                if os.path.splitext(path)[1].lower() == '.opf':
                    self.opfname = path
                    break

    def read(self, path):
        path = path if path else self.opfname
        if self.fs_dict.exists(path):
            return self.fs_dict[path]
        else:
            self.log.warning("file '{}' not exist".format(path))
            return ''
    def write(self, path, data):
        self.fs_dict[path] = data
    def exists(self, path):
        return self.fs_dict.exists(path)
    def namelist(self):
        return self.fs_dict.__iter__()

if __name__ == '__main__':
    file_system = FileSystemDict({
        'file1.txt': 'file1content',
        'dir1': {
            'file2.html': 'file2content',
            'file3.jpg': 'file3content',
            'dir2': {
                'file4.dat': 'file4content'
            }
        },
        'dir5': {}
    })

    file_system['dir1/dir3/newfile.txt'] = 'newcontent'
    #print(file_system['noexists'])
    #print('Output have to be True: {}'.format(file_system.exists('dir1/dir2/file4.dat')))  # 输出: True
    #print('Output have to be False: {}'.format(file_system.exists('dir1/nonexistent/file.jpg')))
    #print(file_system.isdir('dir1/dir2/file4.dat'))
    #file_system.rename('file1.txt', 'dir5/otherfile.txt')
    file_system.delete('dir5')
    print(list(file_system.traverse()))
    #for item in file_system:
    #    print(item)
