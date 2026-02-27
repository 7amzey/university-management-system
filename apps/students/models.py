from django.db import models
from apps.accounts.models import User
from apps.academics.models import College, Major
from apps.courses.models import CourseSection


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
    gender = models.CharField(max_length=10, choices=[('ذكر', 'Male'), ('أنثى', 'Female')], blank=True)
    nationality = models.CharField(max_length=30, blank=True)

    # High school information
    high_school_branch = models.CharField(max_length=50, blank=True)
    high_school_average = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    high_school_country = models.CharField(max_length=50, blank=True)
    high_school_district = models.CharField(max_length=50, blank=True)

    # University information
    student_id = models.CharField(max_length=10, unique=True, null=True, blank=True)
    degree = models.CharField(max_length=50, choices=[
        ('دبلوم', 'Diploma'),
        ('بكالوريوس', 'Bachelor'),
        ('ماجستير', 'Master'),
        ('دكتوراه', 'PhD'),
    ], blank=True)
    college = models.ForeignKey(College, on_delete=models.PROTECT, null=True, blank=True, related_name='students')
    major = models.ForeignKey(Major, on_delete=models.PROTECT, null=True, blank=True, related_name='students')
    funding_entity = models.CharField(max_length=50, choices=[
        ('قرض', 'Loan'),
        ('خاص', 'Private'),
        ('منحة', 'Scholarship'),
    ], blank=True)
    acceptance_type = models.CharField(max_length=50, choices=[
        ('تنافسي', 'Competitive'),
        ('موازي', 'Parallel'),
    ], blank=True)
    study_type = models.CharField(max_length=50, choices=[
        ('نظامي', 'Regular'),
        ('انتساب', 'Affiliation'),
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


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='enrollments')
    section = models.ForeignKey(CourseSection, on_delete=models.PROTECT, related_name='enrollments')
    semester = models.IntegerField(choices=[
        (1, 'First Semester'),
        (2, 'Second Semester'),
        (3, 'Summer Semester'),
    ])
    year = models.IntegerField()

    # Grades
    mid_term_grade = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    participation_grade = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    final_term_grade = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    grade = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('student', 'section')  # student can't enroll in same section twice

    def __str__(self):
        return f"{self.student} - {self.section} ({self.get_semester_display()} {self.year})"