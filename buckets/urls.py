from django.urls import path
from .views import (
    # set_offset_endpoint,
    set_bucket_type_endpoint,
    set_buckets_endpoint,
    query_bucket_name_exist_endpoint,
    get_bucket_detail_endpoint,
    set_bucket_region_endpoint
)

urlpatterns = [
    path('buckets/type', set_bucket_type_endpoint),
    path('buckets/region', set_bucket_region_endpoint),
    path('buckets/bucket', set_buckets_endpoint),
    path('buckets/query_exist', query_bucket_name_exist_endpoint),
    path('buckets/detail', get_bucket_detail_endpoint)
]