from .models import Notification


def notification_context(request):
    """
    Supplies live unread notifications count and recent notifications
    to all templates globally for top navigation bell.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {
            'user_notifications': [],
            'user_unread_notifications_count': 0,
        }

    user = request.user
    user_notifs = Notification.objects.filter(recipient=user).select_related('sender', 'course').order_by('-created_at')
    unread_count = user_notifs.filter(is_read=False).count()
    recent = list(user_notifs[:6])

    return {
        'user_notifications': recent,
        'user_unread_notifications_count': unread_count,
    }

