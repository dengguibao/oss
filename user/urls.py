from django.urls import path
from .views import (
    create_user_endpoint,
    change_password_endpoint,
    user_login_endpoint,
    user_delete_endpoint,
    list_user_info_endpoint,
)

urlpatterns = [
    path('user/register', create_user_endpoint),
    path('user/set_password', change_password_endpoint),
    path('user/delete', user_delete_endpoint),
    path('user/login', user_login_endpoint),
    path('user/list_user', list_user_info_endpoint),
]
