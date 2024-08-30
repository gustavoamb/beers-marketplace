from rest_framework.permissions import BasePermission
from users.models import User


class IsPersonOrVerifiedStore(BasePermission):
    message = "Only Natural Person or verified Stores users can access this resource"

    def has_permission(self, request, view):
        user = request.user
        if user.type == User.Type.PERSON:
            return True

        return user.type == User.Type.STORE and user.store.verified


class IsVerifiedStoreUser(BasePermission):
    message = "Only Verified Stores users can access this resource"

    def has_permission(self, request, view):
        user = request.user
        return user.type == User.Type.STORE and user.store.verified


class IsAdminOrVerifiedStoreUser(BasePermission):
    message = "Only Administrators or verified Stores users can access this resource"

    def has_permission(self, request, view):
        user = request.user
        if user.is_staff:
            return True

        return user.type == User.Type.STORE and user.store.verified


class IsNaturalPersonUser(BasePermission):
    message = "Only Natural Person users can access this resource"

    def has_permission(self, request, view):
        user = request.user
        return user.type == User.Type.PERSON
