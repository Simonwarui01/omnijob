def notifications(request):
    try:
        from core.models import Notification
        count = Notification.objects.filter(is_read=False).count()
        return {'unread_notifications': count}
    except Exception:
        return {'unread_notifications': 0}