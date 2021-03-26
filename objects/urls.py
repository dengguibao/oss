from django.urls import path
from .views import (
    create_directory_endpoint,
    delete_object_endpoint,
)

urlpatterns = [
    path('objects/create_folder', create_directory_endpoint),
    path('objects/delete', delete_object_endpoint)
]
