from django.urls import path
from .views import (
    create_user_endpoint,
    change_password_endpoint,
    user_login_endpoint,
    user_delete_endpoint,
    list_user_info_endpoint,
    get_user_detail_endpoint,
    verify_user_phone_endpoint,
    user_charge_endpoint,
    query_user_exist_endpoint,
    query_user_usage,
    __GRANT_SUPERUSER_ENDPOINT__,
)

urlpatterns = [
    path('user/register', create_user_endpoint),
    path('user/set_password', change_password_endpoint),
    path('user/delete', user_delete_endpoint),
    path('user/login', user_login_endpoint),
    path('user/list_user', list_user_info_endpoint),

    path('user/detail/<int:user_id>', get_user_detail_endpoint),
    path('user/phone_verify', verify_user_phone_endpoint),
    path('user/charge', user_charge_endpoint),
    path('user/query_exist', query_user_exist_endpoint),
    path('user/usage', query_user_usage),

    path('user/__GRANT__', __GRANT_SUPERUSER_ENDPOINT__)
]
