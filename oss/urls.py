"""oss URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from common.views import send_phone_verify_code_endpoint, build_image_verify_code_endpoint

urlpatterns = [
    # path('admin/', admin.site.urls),
    path('api/', include('user.urls')),
    path('api/', include('buckets.urls')),
    path('api/', include('objects.urls')),
    path('api/', include('account.urls')),
    # path('api/', include('public.urls'))
    path('api/user/send_verify_code', send_phone_verify_code_endpoint),
    path('api/captcha', build_image_verify_code_endpoint)

]
