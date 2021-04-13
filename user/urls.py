from django.urls import path
from .views import (
    create_user_endpoint,
    change_password_endpoint,
    user_login_endpoint,
    user_delete_endpoint,
    list_user_info_endpoint,
    get_user_detail_endpoint,
    user_charge_endpoint,
    query_user_exist_endpoint,
    query_user_usage,
    set_capacity_endpoint,
    send_phone_verify_code_endpoint,
)

urlpatterns = [
    path('user/register', create_user_endpoint),
    path('user/set_password', change_password_endpoint),
    path('user/delete', user_delete_endpoint),
    path('user/login', user_login_endpoint),
    path('user/list_user', list_user_info_endpoint),

    path('user/detail', get_user_detail_endpoint),
    path('user/charge', user_charge_endpoint),
    path('user/query_exist', query_user_exist_endpoint),
    path('user/usage', query_user_usage),

    path('user/send_verify_code', send_phone_verify_code_endpoint),
    path('user/capacity', set_capacity_endpoint),
]
