from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import MD5
import base64
import json
import time

private_key = '''-----BEGIN OPENSSH PRIVATE KEY-----
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
BAUGBw==
-----END OPENSSH PRIVATE KEY-----
'''

public_key = '''ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDXR+eGIExJpIUn3kN
lZfdFdtwQEjF72uKQBiSiVHtyilS3jXiCjHXGixQV/RMiPet/SuFwgMhUl+F+TdPrff7D4Y
Eke2JSWerDSOtf5+55uZdBnGqoFKt8q71/zl2O9WunNSSYNkaoFICx7vC1nkCE7vSyyxB2d
BzkisS0kJG65DItFeb3YsGzEwtB54MgnOhjhuHuur1741yEa4MRVuXN6QluwSkjGVEgYEG9
uX60mLEO3TaZmeqYS0Y3STy/M5OnQUj6wOI8Ht0lHZzdDJtBn55ZdI8Kn0eu7BCCUxMsXeX
xSYTnXdcXEwWWjrzXN+mB07nDYJP3q693UMiaZkyjNkQEv+I1FmlkgAzsqnsID74LS43HGq
7CR92Vn9eopDyNeXK+WBE6nQbgldldxZ4blZ1VoWV6dqdB55EiG9SxzbEK8ToKS6dI6o7eF
FODLy7eKFro0yUrJR62fzwxg+HCG07Hmo+h++8ers56PO6f1Ghe4EDNlUHvZWjcOeGuzu8=
'''


def sign(data):
    priKey = RSA.importKey(private_key)
    signer = PKCS1_v1_5.new(priKey)
    hash_obj = MD5.new(data.encode())
    _signature = base64.b64encode(signer.sign(hash_obj))
    return _signature


def verify(signature, data):
    pubKey = RSA.importKey(public_key)
    h = MD5.new(data.encode())
    verifier = PKCS1_v1_5.new(pubKey)
    return verifier.verify(h, base64.b64decode(signature))


now = int(time.time())
days = 10

user_license = {
    'max_users': 5,
    'max_bucket': 100,
    'max_capacity': 40960,
    'start_time': now,
    'end_time': now+(86400*days),
    'info': 'test co.ltd'
}

signature = sign(json.dumps(user_license))
if verify(signature, json.dumps(user_license)):
    user_license['signature'] = signature.decode()
    with open('license.lic', 'wb') as fp:
        fp.write(json.dumps(user_license).encode())
    print('success')
else:
    print('failed')
