from django.urls import path
from .views import (
    create_directory_endpoint,
    delete_object_endpoint,
    list_objects_endpoint,
    put_object_endpoint,
    download_object_endpoint,
    set_object_perm_endpoint,
    query_object_perm_endpoint,
    set_object_acl_endpoint,
)

urlpatterns = [
    path('objects/create_folder', create_directory_endpoint),
    path('objects/delete', delete_object_endpoint),
    path('objects/list_objects', list_objects_endpoint),
    path('objects/upload_file', put_object_endpoint),
    path('objects/download_file', download_object_endpoint),
    path('objects/set_perm', set_object_perm_endpoint),
    path('objects/query_perm', query_object_perm_endpoint),
    path('objects/acl', set_object_acl_endpoint)
]
