import json
import logging
import time
from logging import handlers
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import MD5
import base64
import os
import threading

public_key = '''ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDXR+eGIExJpIUn3kN
lZfdFdtwQEjF72uKQBiSiVHtyilS3jXiCjHXGixQV/RMiPet/SuFwgMhUl+F+TdPrff7D4Y
Eke2JSWerDSOtf5+55uZdBnGqoFKt8q71/zl2O9WunNSSYNkaoFICx7vC1nkCE7vSyyxB2d
BzkisS0kJG65DItFeb3YsGzEwtB54MgnOhjhuHuur1741yEa4MRVuXN6QluwSkjGVEgYEG9
uX60mLEO3TaZmeqYS0Y3STy/M5OnQUj6wOI8Ht0lHZzdDJtBn55ZdI8Kn0eu7BCCUxMsXeX
xSYTnXdcXEwWWjrzXN+mB07nDYJP3q693UMiaZkyjNkQEv+I1FmlkgAzsqnsID74LS43HGq
7CR92Vn9eopDyNeXK+WBE6nQbgldldxZ4blZ1VoWV6dqdB55EiG9SxzbEK8ToKS6dI6o7eF
FODLy7eKFro0yUrJR62fzwxg+HCG07Hmo+h++8ers56PO6f1Ghe4EDNlUHvZWjcOeGuzu8=
'''

lock = threading.Lock()


def validate_local_time():
    clock = get_clock()
    if 0 <= time.time() < clock:
        return False

    t = threading.Thread(target=write_clock, args=())
    t.setDaemon(True)
    t.start()
    return True


def get_license():
    if not validate_local_time():
        print('local date time not right!')
        exit()

    lic_file = 'license.lic'
    if not os.path.exists(lic_file):
        print('not found license')
        exit()

    with open(lic_file, 'rb') as fp:
        lic_content = fp.read().decode()
    if not lic_content:
        print('license is empty')
        exit()

    lic_data = None
    try:
        lic_data = json.loads(lic_content)
        sig = lic_data['signature']
        del lic_data['signature']

        if not verify(sig, json.dumps(lic_data)):
            print('license signature wrong!')
            exit()

        if lic_data['start_time'] > time.time() or time.time() > lic_data['end_time']:
            print('license is expired!')
            lic_data['expire'] = True
            # exit()
        else:
            lic_data['expire'] = False

    except KeyError:
        print('license content format wrong!')
        exit()

    except json.decoder.JSONDecodeError:
        print('license content wrong!')
        exit()

    return lic_data


def verify(signature: str, data: str):
    rsa_pub_key = RSA.importKey(public_key)
    h = MD5.new(data.encode())
    verifier = PKCS1_v1_5.new(rsa_pub_key)
    return verifier.verify(h, base64.b64decode(signature))


def get_logger() -> logging.Logger:
    if not os.path.isdir('./logs') or not os.path.exists('./logs'):
        os.mkdir('./logs')
    logger = logging.getLogger(__name__)
    log_filename = './logs/web.log'
    th = handlers.TimedRotatingFileHandler(log_filename, when='MIDNIGHT', interval=1, encoding='utf-8')
    log_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    th.setFormatter(log_fmt)
    th.suffix = '%Y%m%d.log'
    logger.setLevel(logging.INFO)
    logger.addHandler(th)
    return logger


def get_clock() -> int:
    if not os.path.exists('./oss/clock.dat'):
        return -1
    try:
        with open('./oss/clock.dat', 'rb') as fp:
            return int(fp.read().decode())
    except ValueError:
        return -1


def get_db_config() -> dict:
    if not os.path.exists('db.json'):
        return dict()

    with open('db.json', 'rb') as fp:
        data = fp.read()

    try:
        j = json.loads(data)
    except json.JSONDecodeError:
        return dict()
    else:
        return j


def write_clock() -> None:
    now = int(time.time())
    while True:
        lock.acquire()
        with open('./oss/clock.dat', 'wb') as fp:
            fp.write(str(now).encode())
        lock.release()
        now += 1
        time.sleep(1)
