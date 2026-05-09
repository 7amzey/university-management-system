from django.db.models import Q
from django.utils import timezone

# Context processor to count unseen announcements for a student
def announcement_count(request):
    if not request.user.is_authenticated:
        return {}
    if not hasattr(request.user, 'student_profile'):
        return {}

    student = request.user.student_profile
    last_seen = student.announcements_last_seen

    from apps.announcements.models import Announcement
    query = Q(student=student) | Q(student__isnull=True)

    if last_seen:
        query &= Q(created_at__gt=last_seen)

    count = Announcement.objects.filter(query).count()
    return {'unseen_announcements': count}