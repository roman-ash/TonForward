from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from user.views import MyObtainTokenPairView, RegisterView, UserViewSet

app_name = 'user'

router = DefaultRouter()

router.register('', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # path('', UserViewSet.as_view(), name='user'),
    path('login/', MyObtainTokenPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='auth_register'),
]