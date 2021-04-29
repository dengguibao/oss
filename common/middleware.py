from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin
import json
from .func import get_client_ip
from django.conf import settings


class RequestLogMiddleware(MiddlewareMixin):

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.get_response = get_response
        self.logger = settings.LOGGER

    def __call__(self, request):

        try:
            if request.content_type == 'multipart/form-data':
                body = request.POST.dict()
                file = request.FILES.get('file', None)
                body['file'] = str(file)
            else:
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
            url = request.path+'?'+query_string
        else:
            url = request.path
        msg = {
            'body': None if not body else json.dumps(body, ensure_ascii=False).replace('"', '\''),
            'url': url,
            'method': request.method,
            'user': request.user.username if not isinstance(request.user, AnonymousUser) else 'AnonymousUser',
            'source_ip': get_client_ip(request),
            # 'destination_ip': socket.gethostbyname(socket.gethostname()),
            'response_status_code': response.status_code,
            'content-length': len(response.content) if hasattr(response, 'content') else -1
        }
        self.logger.info(json.dumps(msg, ensure_ascii=False)[1:-1].replace('"', ''))

        return response

    @staticmethod
    def filter_secure_data(body: dict, fields: tuple) -> dict:
        for f in fields:
            if f in body:
                body[f] = '******'
        return body
