#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Author: cdhigh<https://github.com/cdhigh>
import os, uuid, shutil

#模拟文件系统目录树结构的一个字典类
#file_system = FileSystemDict()
#file_system['dir1/dir2/file4.txt'] = 'content'
#print(file_system['dir1/dir2/file4.txt'])
class FileSystemDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dirs = set() #保留各个目录，用于确定目录是否存在
        self._update_dirs()
        
    def __getitem__(self, key_path):
        key = key_path.replace('\\', '/').rstrip('/')
        try:
            return dict.__getitem__(self, key)
        except:
            return b''

    def __setitem__(self, key_path: str, value):
        key_path = key_path.replace('\\', '/').rstrip('/')
        dict.__setitem__(self, key_path, value)
        keys = key_path.split('/') #添加目录列表
        for idx in range(1, len(keys)):
            self.dirs.add('/'.join(keys[:idx]))
    
    #判断一个路径或文件是否存在
    def exists(self, key_path: str):
        key = key_path.replace('\\', '/').rstrip('/')
        return key in (list(self.keys()) + list(self.dirs))
    
    #判断是否是目录文件并且是否存在
    def isdir(self, key_path: str):
        return key_path.replace('\\', '/').rstrip('/') in self.dirs
    def isfile(self, key_path: str):
        return key_path.replace('\\', '/').rstrip('/') in self.keys()
    
    #改名，类似linux的mv命令，可以改名，也可以移动文件
    def rename(self, old_path: str, new_path: str):
        old_key = old_path.replace('\\', '/')
        new_key = new_path.replace('\\', '/')
        if self.exists(old_key):
            value = self.pop(old_key)
            self[new_key] = value
            self._update_dirs()
            
    #删除一个文件或目录树
    def delete(self, path: str):
        path = path.replace('\\', '/').rstrip('/')
        if self.isfile(path):
            self.pop(path)
            self._update_dirs()
        #elif self.isdir(path):
        #    for key in path.split('/'):
        #        pass

    #全部清除，释放内存
    def clear(self):
        self.dirs = set()
        for key in list(self.keys()):
            del self[key]

    #将字典的文件缓存保存到一个磁盘目录
    def dump(self, path: str):
        assert(os.path.isabs(path))
        for key, content in self.items():
            file = key[1:] if key.startswith('/') else key
            file_path = os.path.join(path, file)
            file_dir = os.path.dirname(file_path)
            if not os.path.isdir(file_dir):
                os.makedirs(file_dir)
            with open(file_path, 'wb') as f:
                f.write(content)

    #创建一个临时文件名
    @classmethod
    def make_tempfile(self, suffix="", prefix="", dir_='', mode='w+b'):
        return '{}{}{}'.format(prefix, uuid.uuid4(), suffix)

    def __bool__(self):
        return True
    def __str__(self):
        return '/'
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    
    #根据已有文件，重新构建目录列表
    def _update_dirs(self):
        self.dirs = set()
        for key in self.keys():
            keys = key.split('/')
            for idx in range(1, len(keys)):
                self.dirs.add('/'.join(keys[:idx]))
    
    
#提供给OEB的文件读写桩，给外部提供一个统一的文件系统接口，内部根据情况使用模拟文件系统字典或调用系统函数
class FsDictStub(object):
    #path: 如果path=str，则使用操作系统文件读写，否则使用path对应的FileSystemDict读写
    def __init__(self, path=None, log=None, ignore_opf=False):
        if path:
            assert(os.path.isabs(path))
            self.path = path
            self.fs_dict = None
        else:
            self.path = '/'
            self.fs_dict = FileSystemDict()
        self.log = log if log else default_log
        self.opfname = None
        if not ignore_opf:
            self.find_opf_path()

    @property
    def use_memory_cache(self):
        return self.fs_dict is not None

    def find_opf_path(self):
        for path in self.namelist():
            if os.path.splitext(path)[1].lower() == '.opf':
                self.opfname = path
                break

    def read(self, path, mode='rb'):
        path = path if path else self.opfname
        if not path:
            return b''
        path = os.path.join(self.path, path)
        if self.fs_dict:
            if self.fs_dict.exists(path):
                return self.fs_dict[path]
            else:
                self.log.warning("The file '{}' does not exist".format(path))
                return b''
        else:
            with open(path, mode) as f:
                return f.read()

    def write(self, path, data, mode='wb'):
        path = os.path.join(self.path, path)
        if self.fs_dict:
            self.fs_dict[path] = data
        else:
            dir_ = os.path.dirname(path)
            if not os.path.isdir(dir_):
                os.makedirs(dir_)
            with open(path, mode) as f:
                f.write(data)

    #删除一个文件
    def delete(self, path):
        path = os.path.join(self.path, path)
        if self.fs_dict:
            self.fs_dict.delete(path)
        else:
            try:
                os.remove(path)
            except:
                pass

    #改名，类似linux的mv命令，可以改名，也可以移动文件
    def rename(self, old_path, new_path):
        old_path = os.path.join(self.path, old_path)
        new_path = os.path.join(self.path, new_path)
        if self.fs_dict:
            self.fs_dict.rename(old_path, new_path)
        else:
            if os.path.exists(new_path):
                os.remove(new_path)
            os.rename(old_path, new_path)

    #创建多级目录
    def makedirs(self, path):
        if not self.fs_dict:
            path = os.path.join(self.path, path)
            if not os.path.isdir(path):
                os.makedirs(path)
    mkdir = makedirs

    def exists(self, path):
        path = os.path.join(self.path, path)
        return self.fs_dict.exists(path) if self.fs_dict else os.path.exists(path)
    def isfile(self, path):
        path = os.path.join(self.path, path)
        return self.fs_dict.isfile(path) if self.fs_dict else os.path.isfile(path)
    def isdir(self, path):
        path = os.path.join(self.path, path)
        return self.fs_dict.isdir(path) if self.fs_dict else os.path.isdir(path)
    def __str__(self):
        return self.path
    def clear(self):
        if self.fs_dict:
            self.fs_dict.clear()
        elif self.path != '/':
            try:
                shutil.rmtree(self.path, ignore_errors=True)
            except:
                pass

    def namelist(self):
        if self.fs_dict:
            return self.fs_dict.keys()
        else:
            names = []
            base = self.path
            for root, dirs, files in os.walk(base):
                for fname in files:
                    fname = os.path.join(root, fname).replace('\\', '/')
                    names.append(fname)
            return names

    #创建一个文件读写锁
    def createRLock(self):
        import threading
        return fakeRLock() if self.fs_dict else threading.RLock()

    #创建一个临时文件对象，这个临时文件对象可以使用with语句
    def make_tempfile(self, *args, **kwargs):
        if self.fs_dict:
            stub = StubTemporaryFile(*args, **kwargs)
            stub.fs = self
            return stub
        else:
            from calibre.ptempfile import PersistentTemporaryFile
            return PersistentTemporaryFile(*args, **kwargs)

    #遍历指定目录，不包含子目录，dir_为空则遍历内部指定的根目录
    def listdir(self, dir_=None):
        dir_ = dir_ if dir_ else self.path
        if self.fs_dict:
            result = []
            for item in self.fs_dict.keys():
                item = item.lstrip(dir_).lstrip('/')
                if '/' not in item:
                    result.append(item) #和os.listdir()一致，返回相对路径
            return result
        else:
            return os.listdir(dir_)

    #遍历指定目录及其子目录，逐一返回文件名
    #dir_=None: 遍历内部指定的根目录
    #relpath=True: 返回相对于fs根目录的相对目录
    def walk(self, dir_=None, relpath=False):
        dir_ = dir_ if dir_ else self.path
        if self.fs_dict:
            if self.fs_dict.isfile(dir_):
                yield os.path.relpath(dir_, self.path) if relpath else dir_
            else:
                dir_ = dir_.replace('\\', '/')
                dir_ = dir_ if dir_.endswith('/') else dir_ + '/'
                for key in self.fs_dict.keys():
                    if key.startswith(dir_):
                        yield os.path.relpath(key, self.path) if relpath else key
        else:
            if os.path.isfile(dir_):
                yield os.path.relpath(dir_, self.path) if relpath else dir_
            else:
                for spec in os.walk(dir_):
                    root, files = spec[0], spec[-1] #root, dirs, files
                    for name in files:
                        path = os.path.join(root, name)
                        if os.path.isfile(path):
                            yield os.path.relpath(path, self.path) if relpath else path

    #切换当前目录的上下文函数
    def current_dir(self, path):
        if self.fs_dict:
            return fakeCurrentDir(path)
        else:
            from calibre import CurrentDir
            return CurrentDir(path)

    #删除指定目录下所有文件和子目录，但不删除指定的目录本身
    def clear_dir(self, path):
        if not self.fs_dict:
            for x in os.listdir(path):
                shutil.rmtree(x) if os.path.isdir(x) else os.remove(x)

    #支持通配符的查询指定目录下的文件，返回一个符合条件的文件全路径名列表
    #当前支持*和?
    def glob(self, path):
        if self.fs_dict:
            return [item for item in self.fs_dict.keys() if is_wildcard_match(item, path)]
        else:
            import glob
            return glob.glob(path)

    def dump(self, path):
        if self.fs_dict:
            self.fs_dict.dump(path)
        else:
            try:
                shutil.copytree(self.path, path)
            except Exception as e:
                print(e)

#一个假的threading.RLock
class fakeRLock:
    def acquire(self, blocking=True, timeout=- 1):
        pass
    def release(self):
        pass
    def __enter__(self):
        return self.acquire()
    def __exit__(self, type=None, value=None, traceback=None):
        return self.release()

#一个假的临时文件类
class StubTemporaryFile:
    #fs: FileSystemDict 实例
    def __init__(self, suffix="", prefix="", dir=None, mode='w+b'):
        self.fs = None
        self.filename = FileSystemDict.make_tempfile(suffix=suffix, prefix=prefix, dir_=dir, mode=mode)
    def __enter__(self):
        return self
    def __exit__(self, type=None, value=None, traceback=None):
        return
    def write(self, data, mode='wb'):
        self.fs.write(self.filename, data, mode)
    @property
    def name(self):
        return os.path.join(self.fs.path, self.filename)

#一个假的切换当前目录类，可以使用with
class fakeCurrentDir:
    def __init__(self, path=None):
        self.path = path
    def __enter__(self, *args):
        return '/'
    def __exit__(self, *args):
        return

#支持通配符的字符串匹配函数，判断输入的字符串 s 是否满足 p 的要求
#通配符支持'*'和'?'，比如 a* 匹配 ab,abc, a?只匹配ab，不匹配abc
def is_wildcard_match(s: str, p: str):
    m, n = len(s), len(p)
    dp = [[False] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = True
    
    for j in range(1, n + 1):
        if p[j - 1] == '*':
            dp[0][j] = dp[0][j - 1]
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if p[j - 1] == s[i - 1] or p[j - 1] == '?':
                dp[i][j] = dp[i - 1][j - 1]
            elif p[j - 1] == '*':
                dp[i][j] = dp[i][j - 1] or dp[i - 1][j]
    
    return dp[m][n]


#第一个版本的FileSystemDict，有点复杂，现在改成上面的版本
class FileSystemDict1(dict):
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

    #创建一个临时文件名
    @classmethod
    def make_tempfile(self, suffix="", prefix="", dir_='', mode='w+b'):
        return '{}{}{}'.format(prefix, uuid.uuid4(), suffix)

    def __bool__(self):
        return True
    def __str__(self):
        return '/'
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass

if __name__ == '__main__':
    value = os.path.join('/', 'dir')
    fs1 = FileSystemDict1({
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
    fs1['dir1/dir3/newfile.txt'] = 'newcontent'
    
    fs = FileSystemDict({'file1.txt': 'file1content', 'dir1/file2.html': 'file2content', 
                         '/dir1/dir2/file4.dat': 'file4content', 'dir5': {}})
    
    print(fs['noexists'])
    print('Output have to be True: {}'.format(fs.exists('/dir1/dir2/')))  # 输出: True
    print('Output have to be False: {}'.format(fs.exists('dir1/nonexistent/file.jpg')))
    #print(fs.isdir('dir1/dir2/file4.dat'))
    #fs.rename('file1.txt', 'dir5/otherfile.txt')
    #fs.delete('dir5')
    #print(list(fs.traverse()))
    #for item in fs:
    #    print(item)
