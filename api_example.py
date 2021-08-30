import requests
from enum import Enum


class Permission(Enum):
    PRIVATE = 'private'
    PUBLIC_READ = 'public-read'
    PUBLIC_READ_WRITE = 'public-read-write'
    AUTHENTICATED = 'authenticated'


class Oss:
    session = requests.session()

    def __init__(self, access_key: str, secret_key: str, server: str):
        self.ak = access_key
        self.sk = secret_key
        if not server.startswith('https://') and not server.startswith('http://'):
            exit('server address must be start with http:// or https://')

        self.server = server

    def create_directory(self, bucket_name: str, folder_name: str, path_key_url=None):
        """
        在桶内创建目录，不指定路径则创建在桶的根目录下
        """
        post_data = {
            'bucket_name': bucket_name,
            'folder_name': folder_name,
        }
        # 根目录不需要填写该参数
        if path_key_url:
            post_data['path'] = path_key_url

        rep = self.session.post(
            '%s/api/objects/create_folder' % self.server,
            json=post_data,
            params={
                'access_key': self.ak,
                'secret_key': self.sk
            },
        )
        return rep.json()

    def upload_file_to_bucket(self, bucket_name: str, file: str, path_key_url: str = None, perm: Permission = None):
        """
        上传对象至指定的桶，如果指定路径则上传文件至指定的目录下，不指定则上传至根目录
        不指定文件权限则上传文件的访问权限继续桶的访问权限
        """
        post_data = {
            'bucket_name': bucket_name
        }

        if perm:
            post_data['permission'] = perm

        if path_key_url:
            post_data['path'] = path_key_url

        rep = self.session.put(
            '%s/api/objects/upload_file' % self.server,
            data=post_data,
            files={
                'file': open(file, 'rb')
            },
            params={
                'access_key': self.ak,
                'secret_key': self.sk
            }
        )
        return rep.json

    def list_objects_by_bucket(self, bucket_name: str, path_key_url: str = None, page_size: int = 10, page: int = 1):
        params = {
            'access_key': self.ak,
            'secret_key': self.sk,
            'bucket_name': bucket_name,
            'path': path_key_url,
            'page': page,
            'page_size': page_size
        }
        rep = self.session.get(
            '%s/api/objects/list_objects' % self.server,
            params=params
        )
        return rep.json()

    def delete_file_by_bucket(self, bucket_name: str, key_url: str):
        rep = self.session.delete(
            '%s/api/objects/delete' % self.server,
            params={
                'access_key': self.ak,
                'secret_key': self.sk,
                'bucket_name': bucket_name,
                'key': key_url
            }
        )
        return rep.json()

    def generate_download_url(self, bucket_name: str, key_url: str):
        rep = self.session.post(
            '%s/api/objects/generate_download_url' % self.server,
            json={
                'bucket_name': bucket_name,
                'key': key_url
            },
            params={
                'access_key': self.ak,
                'secret_key': self.sk
            }
        )
        return rep.json()

    def download_file_by_bucket(self, bucket_name: str, key_url: str):
        rep = self.session.get(
            '%s/api/objects/download_file' % self.server,
            params={
                'access_key': self.ak,
                'secret_key': self.sk,
                'bucket_name': bucket_name,
                'key': key_url
            }
        )
        return rep.content


o = Oss(
    access_key='QCbqZSvWfKM8PkX67Uc1GtTNgdyw9R4a',
    secret_key='qULruwWOTgAP0B6oZnGF451JMyCiRdktN2DVEcbS',
    server='http://127.0.0.1:8000'
)
result = o.list_objects_by_bucket('bbb')
print(result)

# 在指定的桶内（指定的目录）创建目录
# result = o.create_directory(
#     bucket_name='bbb',
#     folder_name='ccc'
# )
# print(result)

# 上传文件到指定的桶
# result = o.upload_file_to_bucket(
#     bucket_name='bbb',
#     file='test.py',
#     path_key_url='Y2NjLw=='
# )
# print(result)

# 删除指定桶内的文件
# result = o.delete_file_by_bucket(
#     bucket_name='bbb',
#     key_url='Y2NjLw=='
# )
# print(result)

# 生成下载链接有效期5分钟
# result = o.generate_download_url(
#     bucket_name='bbb',
#     key_url='dGVzdC5weQ=='
# )
# print(result)

# 下载比特流到打定的文件
# fp = open('aaa.py', 'wb+')
# fp.write(o.download_file_by_bucket(
#     bucket_name='bbb',
#     key_url='dGVzdC5weQ=='
# ))
# fp.close()
