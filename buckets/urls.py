from django.urls import path
from .views import (
    set_offset_endpoint,
    set_bucket_type_endpoint,
)

urlpatterns = [
    path('buckets/type', set_bucket_type_endpoint),
    path('buckets/offset', set_offset_endpoint),
]