import socket

from django.utils.deprecation import MiddlewareMixin
import json
import logging
import threading

local = threading.local()


class RequestLogMiddleware(MiddlewareMixin):
    """
    将request的信息记录在当前的请求线程上。
    """

    def __init__(self, get_response=None):
        self.get_response = get_response
        self.apiLogger = logging.getLogger('./logs/web.log')

    def __call__(self, request):

        try:
            body = json.loads(request.body)
        except json.decoder.JSONDecodeError:
            body = dict()

        if request.method == 'GET':
            body.update(dict(request.GET))
        else:
            body.update(dict(request.POST))

        local.body = body
        local.path = request.path
        local.method = request.method
        local.username = request.user
        local.sip = request.META.get('REMOTE_ADDR', '')
        local.dip = socket.gethostbyname(socket.gethostname())

        response = self.get_response(request)
        local.status_code = response.status_code
        local.reason_phrase = response.reason_phrase
        print(local.body)
        print(body)
        self.apiLogger.debug('system-auto')

        return response