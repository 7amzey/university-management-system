from django.db import models
from apps.students.models import Student

# Announcement model to store system-generated and admin-created announcements for students
class Announcement(models.Model):
    TRIGGER_TYPES = [
        ('payment_confirmed', 'تأكيد الدفع'),
        ('grades_released', 'إصدار العلامات'),
        ('registration_opened', 'فتح التسجيل'),
        ('custom', 'رسالة مخصصة'),
    ]

    title = models.CharField(max_length=100)
    body = models.TextField()
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='announcements_created',
        null=True, blank=True  # null for system-generated
    )

    # if null — announcement is for ALL students
    # if set — announcement is for this specific student only
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='announcements',
        null=True, blank=True
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        target = self.student or 'الكل'
        return f"{self.get_trigger_type_display()} — {target} — {self.created_at.strftime('%Y-%m-%d')}"