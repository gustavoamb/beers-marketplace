from rest_framework import status, generics
from rest_framework.response import Response
from django.db.models import Q
from stores.models import Purchase

from notifications.models import Notification
from notifications.serializers import NotificationSerializer


# Create your views here.
class NotificationListView(generics.ListAPIView, generics.DestroyAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(receiver=user.id)
        is_purchase_accepted = Q(purchase__status=Purchase.Status.ACCEPTED)
        is_purchase_pending = Q(purchase__status=Purchase.Status.PENDING)
        is_followed_not = Q(type=Notification.Type.FOLLOWED)
        is_received_gift_not = Q(type=Notification.Type.GIFT_RECEIVED)
        return queryset.filter( is_followed_not | (is_received_gift_not & (is_purchase_accepted | is_purchase_pending)  ) ).order_by("-created_at")

    def delete(self, request, *args, **kwargs):
        # Delete all user's notifications
        queryset = self.get_queryset()
        queryset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationMarkAllAsReadView(generics.UpdateAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(receiver=user.id)
        return queryset

    def patch(self, request):
        queryset = self.get_queryset()
        data = [{"read": True} for i in range(queryset.count())]
        serializer = self.serializer_class(queryset, data=data, partial=True, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        notifs_updated = serializer.data
        return Response(notifs_updated, status=status.HTTP_200_OK)
