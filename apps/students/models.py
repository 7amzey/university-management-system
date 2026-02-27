from django.db import models
from apps.accounts.models import User
from apps.academics.models import College, Major
from apps.courses.models import CourseSection
from django.core.exceptions import ValidationError
from django.db.models import Sum


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')

    # Name in English
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    father_name = models.CharField(max_length=30, blank=True)
    grandfather_name = models.CharField(max_length=30, blank=True)

    # Name in Arabic
    first_name_ar = models.CharField(max_length=30, blank=True)
    father_name_ar = models.CharField(max_length=30, blank=True)
    grandfather_name_ar = models.CharField(max_length=30, blank=True)
    last_name_ar = models.CharField(max_length=30, blank=True)

    # Personal information
    national_id = models.CharField(max_length=10, unique=True, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    birth_place = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=10, choices=[('Male', 'ذكر'), ('Female', 'أنثى')], blank=True)
    nationality = models.CharField(max_length=30, blank=True)

    # High school information
    high_school_branch = models.CharField(max_length=50, blank=True)
    high_school_average = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    high_school_country = models.CharField(max_length=50, blank=True)
    high_school_district = models.CharField(max_length=50, blank=True)

    # University information
    student_id = models.CharField(max_length=10, unique=True, null=True, blank=True)
    degree = models.CharField(max_length=50, choices=[
        ('Diploma', 'دبلوم'),
        ('Bachelor', 'بكالوريوس'),
        ('Master', 'ماجستير'),
        ('PhD', 'دكتوراه'),
    ], blank=True)
    college = models.ForeignKey(College, on_delete=models.PROTECT, null=True, blank=True, related_name='students')
    major = models.ForeignKey(Major, on_delete=models.PROTECT, null=True, blank=True, related_name='students')
    funding_entity = models.CharField(max_length=50, choices=[
        ('Loan', 'قرض'),
        ('Private', 'خاص'),
        ('Scholarship', 'منحة'),
    ], blank=True)
    acceptance_type = models.CharField(max_length=50, choices=[
        ('Competitive', 'تنافسي'),
        ('Parallel', 'موازي'),
    ], blank=True)
    study_type = models.CharField(max_length=50, choices=[
        ('Regular', 'نظامي'),
        ('Affiliation', 'انتساب'),
    ], blank=True)
    enrollment_year = models.IntegerField(null=True, blank=True)

    # Contact
    phone_number = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return f"({self.student_id}) {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.father_name} {self.grandfather_name} {self.last_name}"

    @property
    def full_name_ar(self):
        return f"{self.first_name_ar} {self.father_name_ar} {self.grandfather_name_ar} {self.last_name_ar}"

    @property
    def gpa(self):
        enrollments = self.enrollments.filter(grade__isnull=False)
        if not enrollments.exists():
            return None
        total = sum(e.grade * e.section.subject.hours for e in enrollments)
        hours = sum(e.section.subject.hours for e in enrollments)
        return round(total / hours, 2) if hours > 0 else None
    
    @property
    def balance(self):
        from django.db.models import Sum
        from finance.models import Transaction
        charges = self.transactions.filter(transaction_type='charge').aggregate(
            total=Sum('amount'))['total'] or 0
        payments = self.transactions.filter(transaction_type='payment').aggregate(
            total=Sum('amount'))['total'] or 0
        return payments - charges


# add this to students/models.py
class HourRegistration(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='hour_registrations')
    semester = models.IntegerField(choices=[
        (1, 'First Semester'),
        (2, 'Second Semester'),
        (3, 'Summer Semester'),
    ])
    year = models.IntegerField()
    requested_hours = models.IntegerField()
    is_paid = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'semester', 'year')

    def __str__(self):
        return f"{self.student} - {self.requested_hours} hrs ({self.get_semester_display()} {self.year})"


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='enrollments')
    section = models.ForeignKey(CourseSection, on_delete=models.PROTECT, related_name='enrollments')
    hour_registration = models.ForeignKey(
        HourRegistration,
        on_delete=models.PROTECT,
        related_name='enrollments',
        null=True
    )  # replaces standalone semester and year fields
    mid_term_grade = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    participation_grade = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    final_term_grade = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    grade = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('student', 'section')

    def __str__(self):
        return f"{self.student} - {self.section} ({self.hour_registration.get_semester_display()} {self.hour_registration.year})"
    
    def clean(self):
        # Rule 1: student must have paid before enrolling
        if not self.hour_registration.is_paid:
            raise ValidationError('Cannot enroll before paying for registered hours.')

        # Rule 2: enrolled hours must not exceed paid hours
        enrolled_hours = Enrollment.objects.filter(
            student=self.student,
            hour_registration=self.hour_registration
        ).exclude(pk=self.pk).aggregate(
            total=Sum('section__subject__hours')
        )['total'] or 0

        new_hours = self.section.subject.hours

        if enrolled_hours + new_hours > self.hour_registration.requested_hours:
            raise ValidationError(
                f'This would exceed your registered {self.hour_registration.requested_hours} hours. '
                f'You have used {enrolled_hours} hours and this subject requires {new_hours} hours.'
            )