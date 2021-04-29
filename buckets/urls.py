from django.urls import path
from .buckets_perms import set_bucket_perm_endpoint, query_bucket_perm_endpoint
from .buckets_bucket import BucketEndpoint, get_bucket_detail_endpoint, query_bucket_name_exist_endpoint
from .buckets_region import BucketRegionEndpoint
from .buckets_acl import BucketAclEndpoint
from .buckets_type import BucketTypeEndpoint

app_name = 'buckets'

urlpatterns = [
    path('buckets/type', BucketTypeEndpoint.as_view()),
    path('buckets/region', BucketRegionEndpoint.as_view()),
    path('buckets/bucket', BucketEndpoint.as_view()),
    path('buckets/query_exist', query_bucket_name_exist_endpoint),
    path('buckets/detail', get_bucket_detail_endpoint),
    path('buckets/set_perm', set_bucket_perm_endpoint),
    path('buckets/query_perm', query_bucket_perm_endpoint),
    path('buckets/acl', BucketAclEndpoint.as_view()),
]
