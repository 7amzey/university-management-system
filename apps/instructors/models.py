from django.db import models
from apps.accounts.models import User
from apps.academics.models import College, Department

class Instructor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='instructor_profile')

    # Name in English
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)

    # Name in Arabic
    first_name_ar = models.CharField(max_length=30, blank=True)
    last_name_ar = models.CharField(max_length=30, blank=True)

    # Personal information
    national_id = models.CharField(max_length=10, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('ذكر', 'Male'), ('أنثى', 'Female')], blank=True)
    nationality = models.CharField(max_length=30, blank=True)

    # University information
    employee_id = models.CharField(max_length=10, unique=True)
    college = models.ForeignKey(College, on_delete=models.PROTECT, related_name='instructors')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='instructors')
    rank = models.CharField(max_length=50, choices=[
        ('Lecturer', 'محاضر'),
        ('Assistant Professor', 'أستاذ مساعد'),
        ('Associate Professor', 'أستاذ مشارك'),
        ('Professor', 'أستاذ'),
    ], blank=True)

    # Contact
    phone_number = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"