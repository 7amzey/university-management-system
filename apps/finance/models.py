from django.db import models
from apps.students.models import Student

"""
    Transaction model to record all financial transactions related to students, including charges, payments, and refunds.
    Each transaction is linked to a student and includes details such as the type of fee, amount, date, and any relevant notes. 
    The model also tracks whether the transaction was system-generated and if it has been paid.
"""
class Transaction(models.Model):
    FEE_TYPES = [
        ( 'registration','رسوم تسجيل'),
        ('semester', 'رسوم فصل'),
        ('late', 'رسوم تأخير'),
        ('clinic', 'رسوم استخدام العيادة'),
        ('transcript', 'رسوم اصدار اثبات طالب'),
        ('clearance', 'رسوم براءة ذمة'),
        ('other', 'رسوم أخرى'),
    ]
    TRANSACTION_TYPES = [
        ('charge', 'مستحق'),
        ('payment', 'مدفوع'),
        ('refund', 'مسترد'),
    ]

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    fee_type = models.CharField(max_length=50, choices=FEE_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    semester = models.IntegerField(choices=[
        (1, 'الفصل الأول'),
        (2, 'الفصل الثاني'),
        (3, 'الفصل الصيفي'),
    ], null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    note = models.TextField(blank=True)
    is_system_generated = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)
    is_service = models.BooleanField(default=False)
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