from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from main.views import serve_media

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Прод (PythonAnywhere): файлы лежат на диске, поэтому /media/
    # нужно отдавать самим — иначе при DEBUG=False будет 404.
    urlpatterns += [
        path('media/<path:file_path>', serve_media, name='serve_media'),
    ]