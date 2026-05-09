from django.db.models.signals import post_save
from django.dispatch import receiver

# payment confirmed
# This signal is triggered when a HourRegistration instance is saved with is_paid=True and paid_hours > 0.
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