from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from rest_framework_swagger.views import get_swagger_view
from rest_framework import permissions
from drf_yasg import views, openapi
from django.http import HttpResponse



schema_view = get_swagger_view(title="APIs")

redoc_schema_view = views.get_schema_view(
   openapi.Info(
      title="APIs",
      default_version='v1',
      description="API Documentation",
      terms_of_service="#",
   ),
   public=True,
)



def myindex(request):
    return HttpResponse("backend server is running")


urlpatterns = [
    path('docs/', redoc_schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', redoc_schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('admin/', admin.site.urls),
    path('api/', include('app.urls')),
    path('', myindex, name='index')
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
