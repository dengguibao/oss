from django.urls import path
from .views import(
    put_object_endpoint,
    delete_object_endpoint,
    download_object_endpoint,
    # multi_part_upload_endpoint,
    list_all_objects,
)

urlpatterns = [
    path('public/upload', put_object_endpoint),
    # path('public/multipart/<str:stage>', multi_part_upload_endpoint),
    path('public/delete', delete_object_endpoint),
    path('public/download', download_object_endpoint),
    path('public/list', list_all_objects)
]