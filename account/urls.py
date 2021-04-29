from django.urls import path
from .account_plan import PlanEndpoint
from .account_order import OrderEndpoint


app_name = 'account'

urlpatterns = [
    path('account/plan', PlanEndpoint.as_view()),
    path('account/order', OrderEndpoint.as_view())
]
