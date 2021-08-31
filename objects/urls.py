from django.urls import path
from .objects_perms import query_object_perm_endpoint, set_object_perm_endpoint
from .objects_acl import ObjectAclEndpoint
from .objects_object import (
    create_directory_endpoint,
    delete_object_endpoint,
    list_objects_endpoint,
    upload_file_to_bucket_endpoint,
    download_object_endpoint,
    generate_download_url_endpoint,
    put_object_to_bucket_endpoint,
)
app_name = 'objects'

urlpatterns = [
    path('objects/create_folder', create_directory_endpoint),
    path('objects/delete', delete_object_endpoint),
    path('objects/list_objects', list_objects_endpoint),
    path('objects/upload_file', upload_file_to_bucket_endpoint),
    path('objects/put_object', put_object_to_bucket_endpoint),
    path('objects/download_file', download_object_endpoint),
    path('objects/set_perm', set_object_perm_endpoint),
    path('objects/query_perm', query_object_perm_endpoint),
    path('objects/acl', ObjectAclEndpoint.as_view()),
    path('objects/generate_download_url', generate_download_url_endpoint),

]
