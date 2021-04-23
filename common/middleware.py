import os
import socket
import time
from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin
import json
import logging
from logging import handlers


# import threading

# local = threading.local()


class RequestLogMiddleware(MiddlewareMixin):

    def __init__(self, get_response=None):
        self.get_response = get_response
        # self.apiLogger = logging.getLogger('./logs/web.log')

        logger = logging.getLogger()
        log_filename = './logs/web.log'

        # fh = logging.FileHandler(log_filename, encoding='utf-8', mode='a')
        th = handlers.TimedRotatingFileHandler(log_filename, when='MIDNIGHT', interval=1, encoding='utf-8')

        log_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        th.setFormatter(log_format)

        th.suffix = '.%Y%m%d.log'

        logger.setLevel(logging.INFO)
        # logger.addHandler(fh)
        logger.addHandler(th)
        self.logger = logger

    def __call__(self, request):

        try:
            body = json.loads(request.body)
        except json.decoder.JSONDecodeError:
            body = dict()

        # if request.method == 'GET':
        #     body.update(dict(request.GET))
        # else:
        #     body.update(dict(request.POST))
        response = self.get_response(request)

        body = self.filter_secure_data(body, ('password', 'pwd1', 'pwd2', 'old_pwd'))

        query_string = request.META['QUERY_STRING']
        if query_string:
            url = request.path+'?='+query_string
        else:
            url = request.path
        msg = {
            'body': None if not body else json.dumps(body, ensure_ascii=False).replace('"', '\''),
            'url': url,
            'user': request.user.username if not isinstance(request.user, AnonymousUser) else 'AnonymousUser',
            'source_ip': request.META.get('REMOTE_ADDR', ''),
            'destination_ip': socket.gethostbyname(socket.gethostname()),
            'response_status_code': response.status_code,
            'reason_phrase': response.reason_phrase
        }
        self.logger.info(json.dumps(msg, ensure_ascii=False)[1:-1].replace('"', ''))

        return response

    def filter_secure_data(self,body: dict, fields: tuple) -> dict:
        for f in fields:
            if f in body:
                body[f] = '******'
        return body