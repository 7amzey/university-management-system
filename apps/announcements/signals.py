from django.db.models.signals import post_save
from django.dispatch import receiver

# payment confirmed
from apps.students.models import HourRegistration
@receiver(post_save, sender=HourRegistration, dispatch_uid='announce_payment')
def announce_payment(sender, instance, **kwargs):
    if instance.is_paid and instance.paid_hours > 0:
        from .models import Announcement
        Announcement.objects.get_or_create(
            student=instance.student,
            trigger_type='payment_confirmed',
            defaults={
                'title': 'تم تأكيد الدفع',
                'body': f'تم استيفاء رسوم {instance.paid_hours} ساعة للفصل {instance.get_semester_display()} {instance.year}.'
            }
        )

# grades released — called manually from admin action
def announce_grades_released(section):
    from .models import Announcement
    from apps.students.models import Enrollment
    enrollments = Enrollment.objects.filter(
        section=section,
        symbol__isnull=False
    ).select_related('student')

    for enrollment in enrollments:
        Announcement.objects.create(
            student=enrollment.student,
            trigger_type='grades_released',
            title='تم إصدار العلامات',
            body=f'تم إصدار علامات مادة {section.subject.name} — حصلت على {enrollment.symbol}.'
        )

# registration period opened — called from RegistrationPeriod signal
# from apps.courses.models import RegistrationPeriod
# @receiver(post_save, sender=RegistrationPeriod, dispatch_uid='announce_registration')
# def announce_registration_opened(sender, instance, **kwargs):
#     if instance.is_open:
#         from .models import Announcement
#         from apps.students.models import Student
#         students = Student.objects.all()
#         announcements = [
#             Announcement(
#                 student=None,  # global
#                 trigger_type='registration_opened',
#                 title='فتح باب التسجيل',
#                 body=f'تم فتح باب تسجيل الساعات للفصل {instance.get_semester_display()} {instance.year}. الفترة من {instance.start_date} إلى {instance.end_date}.'
#             )
#         ]
#         Announcement.objects.bulk_create(announcements)