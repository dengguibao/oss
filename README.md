# abount deployment

## install dependent
install python3 environment
#### centos
> yum install python3 python3-pip python-memcached python-pylibmc memcached libjpeg-turbo8

#### ubuntu
> apt install python3 python3-pip python-memcached python-pylibmc memcached libjpeg-turbo8

pip install project dependent  

chdir to project directory, and then install dep

> pip3 install -r ./requirement.txt

## start application
use daphne or uvicorn start app

> daphne oss.asgi:application -b 0.0.0.0 -p 8001

or

> uvicorn oss.asgi:application --port 8001 --host 0


## use mysql database
modify oss/setting.py, change appropriate setting

``` python
DATABASES = {
    # 'default': {
    #     'ENGINE': 'django.db.backends.sqlite3',
    #     'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    # }
    'default': {
        'ENGINE': 'django.db.backends.mysql', # 数据库引擎
        'NAME': 'dms', # 数据库名
        'USER': 'dms', # 账号
        'PASSWORD': '123456', # 密码
        'HOST': '172.31.19.254', # HOST
        'POST': 3306, # 端口
    }
}
```

## package
pip install shiv  
pip install -r requirement.txt --target ./dist  
cp -rf oss user common objects account buckets logs db.sqlite3 manage.py ./dist  
shiv --site-packages dist --compressed -p /usr/bin/env python3 -o oss.pyz -e oss.main  
refer: https://shiv.readthedocs.io/en/latest/django.html