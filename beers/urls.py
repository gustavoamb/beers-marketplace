"""beers URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from common import urls as common_urls
from locations import urls as locations_urls
from notifications import urls as notification_urls
from payments import urls as payments_urls
from stores import urls as stores_urls
from stories import urls as stories_urls
from users import urls as users_urls
from administration import urls as administration_urls

# Special views
from stores.views import GeneralSearchView
from common.views import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("beers/admin/", include(administration_urls.urlpatterns)),
    path("beers/", include(common_urls.urlpatterns)),
    path("beers/", include(payments_urls.urlpatterns)),
    path("beers/", include(stores_urls.urlpatterns)),
    path("beers/", include(users_urls.urlpatterns)),
    path("beers/", include(locations_urls.urlpatterns)),
    path("beers/", include(notification_urls.urlpatterns)),
    path("beers/", include(stories_urls.urlpatterns)),
    path("beers/search/", GeneralSearchView.as_view()),
    path("", HealthCheckView.as_view()),
]
