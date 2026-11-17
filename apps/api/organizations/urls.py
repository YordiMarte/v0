from rest_framework.routers import SimpleRouter

from organizations.views import OrganizationViewSet

router = SimpleRouter()
router.register("organizations", OrganizationViewSet, basename="organization")

urlpatterns = router.urls
