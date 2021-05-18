from django.urls import path
from .user_views import (
    create_user_endpoint,
    change_password_endpoint,
    user_login_endpoint,
    user_delete_endpoint,
    list_user_info_endpoint,
    get_user_detail_endpoint,
    query_user_exist_endpoint,
    query_user_usage,
    get_license_info_endpoint,
)
from .user_account import user_recharge_endpoint
from .user_quota import CapacityQuotaEndpoint, BandwidthQuotaEndpoint
from .user_keys import KeysEndpoint

from .user_group import (
    GroupEndpoint,
    GroupMemberEndpoint,
    GroupPermissionEndpoint,
    list_all_available_perms_endpoint,
    set_default_user_role,
)
app_name = 'user'

urlpatterns = [
    path('user/register', create_user_endpoint),
    path('user/set_password', change_password_endpoint),
    path('user/delete', user_delete_endpoint),
    path('user/login', user_login_endpoint),
    path('user/list_user', list_user_info_endpoint),

    path('user/detail', get_user_detail_endpoint),
    path('user/account/recharge', user_recharge_endpoint),
    path('user/query_exist', query_user_exist_endpoint),
    path('user/usage', query_user_usage),

    path('user/quota/storage', CapacityQuotaEndpoint.as_view()),
    path('user/quota/bandwidth', BandwidthQuotaEndpoint.as_view()),
    # path('user/quota/bandwidth', set_capacity_endpoint),

    path('user/perm/all_perms', list_all_available_perms_endpoint),
    path('user/group/role', GroupEndpoint.as_view()),
    path('user/group/perm', GroupPermissionEndpoint.as_view()),
    path('user/group/role/member', GroupMemberEndpoint.as_view()),

    path('user/role/default', set_default_user_role),

    path('user/keys', KeysEndpoint.as_view()),
    path('license', get_license_info_endpoint),
]
