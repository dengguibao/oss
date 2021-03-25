from rgwadmin import RGWAdmin
from boto3.session import Session
from django.conf import settings


def init_rgw_api():
    access_key, secret_key, server = settings.RGW_API_KEY['NORMAL']
    return RGWAdmin(
        access_key=access_key,
        secret_key=secret_key,
        server=server,
        secure=False,
        verify=False
    )


def init_s3_connection(access_key, secret_key):
    _, _, server = settings.RGW_API_KEY['NORMAL']
    conn = Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
    client = conn.client(
        service_name='s3',
        endpoint_url='http://%s' % server,
        verify=False
    )
    return client
