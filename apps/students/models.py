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
    student_id = models.CharField(max_length=11, unique=True, null=True, blank=True)
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
    academic_status = models.CharField(max_length=50, choices=[
        ('Active', 'على مقاعد الدراسة'),
        ('Graduating', 'متوقع تخرجه'),
        ('Graduated', 'متخرج'),
        ('Suspended', 'موقوف'),
        ('Dropped', 'منسحب'),
    ], blank=True)
    enrollment_year = models.IntegerField(null=True, blank=True)
    # students/models.py inside Student class
    min_hours = models.IntegerField(default=12)
    max_hours = models.IntegerField(default=18)

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
        enrollments = self.enrollments.filter(
            grade_points__isnull=False
        ).select_related('section__subject')

        if not enrollments.exists():
            return 0

        total_points = sum(e.grade_points * e.section.subject.hours for e in enrollments)
        total_hours = sum(e.section.subject.hours for e in enrollments)
        return round(total_points / total_hours, 2) if total_hours > 0 else None
    
    @property
    def balance(self):
        from django.db.models import Sum
        from apps.finance.models import Transaction

        pending = self.transactions.filter(
            transaction_type='charge',
            is_paid=False,
            is_service=False
        ).aggregate(total=Sum('amount'))['total'] or 0

        payments = self.transactions.filter(
            transaction_type='payment',
            is_service=False
        ).aggregate(total=Sum('amount'))['total'] or 0

        refunds = self.transactions.filter(
            transaction_type='refund',
            is_service=False
        ).aggregate(total=Sum('amount'))['total'] or 0

        return payments + refunds - pending

    @property
    def passed_hours(self):
        # F* = 0.5 points, anything above is passing
        return self.enrollments.filter(
            grade_points__isnull=False,
            grade_points__gt=0.5
        ).aggregate(
            total=Sum('section__subject__hours')
        )['total'] or 0

class HourRegistration(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='hour_registrations')
    semester = models.IntegerField(choices=[
        (1, 'الفصل الاول'),
        (2, 'الفصل الثاني'),
        (3, 'الفصل الصيفي'),
    ])
    year = models.IntegerField()
    requested_hours = models.IntegerField()
    is_paid = models.BooleanField(default=False)
    paid_hours = models.IntegerField(default=0)  # tracks how many hours have been paid for

    class Meta:
        unique_together = ('student', 'semester', 'year')

    def __str__(self):
        return f"{self.student} - {self.requested_hours} hrs ({self.get_semester_display()} {self.year})"


class Enrollment(models.Model):

    # Fixed weights for grade calculation
    MID_WEIGHT = 30
    PARTICIPATION_WEIGHT = 20
    FINAL_WEIGHT = 50

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='enrollments')
    section = models.ForeignKey(CourseSection, on_delete=models.PROTECT, related_name='enrollments')
    hour_registration = models.ForeignKey(HourRegistration, on_delete=models.PROTECT, related_name='enrollments',null=True)  # replaces standalone semester and year fields
    
    # raw grades
    mid_term_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    participation_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    final_term_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # auto-calculated
    weighted_total = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # assigned after curve
    symbol = models.CharField(max_length=5, blank=True, null=True)
    grade_points = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('student', 'section')

    def calculate_weighted_total(self):
        if any(g is None for g in [self.mid_term_grade, self.participation_grade, self.final_term_grade]):
            return None
        return (
            (self.mid_term_grade * self.MID_WEIGHT / 100) +
            (self.participation_grade * self.PARTICIPATION_WEIGHT / 100) +
            (self.final_term_grade * self.FINAL_WEIGHT / 100)
        )

    def save(self, *args, **kwargs):
        self.weighted_total = self.calculate_weighted_total()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.section}"

class absence(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='absences')
    count = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Absence for {self.enrollment.student.full_name_ar} on {self.date}"