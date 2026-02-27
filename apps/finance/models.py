from django.db import models
from apps.students.models import Student


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('Charge', 'مطلوب'),
        ('Payment', 'مدفوع'),
    ]

    FEE_TYPES = [
        ('registration', 'رسوم تسجيل'),
        ('semester',     'رسوم فصل'),
        ('late',         'رسوم تأخير'),
        ('clinic',       'رسوم استخدام العيادة'),
        ('transcript',   'رسوم اصدار اثبات طالب'),
        ('clearance',    'رسوم براءة ذمة'),
        ('other',        'رسوم أخرى'),
    ]

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    fee_type = models.CharField(max_length=50, choices=FEE_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    semester = models.IntegerField(choices=[
        (1, 'First Semester'),
        (2, 'Second Semester'),
        (3, 'Summer Semester'),
    ], null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    note = models.TextField(blank=True)
    is_system_generated = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='transactions_created',
        null=True,
        blank=True,
        limit_choices_to={'is_staff': True}
    )

    def __str__(self):
        return f"{self.student} - {self.get_fee_type_display()} - {self.amount} ({self.date.strftime('%Y-%m-%d')})"