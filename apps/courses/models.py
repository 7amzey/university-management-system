from django.db import models
from apps.academics.models import Department, Major
from apps.instructors.models import Instructor
from apps.facilities.models import Room
from .constants import SUBJECT_TYPES


class Subject(models.Model):
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=10, unique=True)
    subject_type = models.CharField(max_length=30, choices=SUBJECT_TYPES, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='subjects')
    majors = models.ManyToManyField(Major, related_name='subjects')
    hours = models.IntegerField()
    prerequisites = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='required_for'
    )

    def __str__(self):
        return f"({self.code}) {self.name}"
    
    def assign_symbols(self, semester, year):
        from apps.students.models import Enrollment

        enrollments = Enrollment.objects.filter(
            section__subject=self,
            section__semester=semester,
            section__year=year,
            weighted_total__isnull=False
        )

        if not enrollments.exists():
            return

        distributions = GradeDistribution.objects.filter(
            subject=self,
            semester=semester,
            year=year
        )

        if not distributions.exists():
            return

        for enrollment in enrollments:
            match = distributions.filter(
                min_grade__lte=enrollment.weighted_total,
                max_grade__gte=enrollment.weighted_total
            ).first()

            if match:
                enrollment.symbol = match.symbol
                enrollment.grade_points = GradeDistribution.SYMBOL_POINTS.get(match.symbol, 0)
            else:
                # weighted_total doesn't fall in any range — assign F*
                enrollment.symbol = 'F*'
                enrollment.grade_points = 0.50

            enrollment.save()


class CourseSection(models.Model):
    SEMESTER_CHOICES = [
        (1, 'الفصل الأول'),
        (2, 'الفصل الثاني'),
        (3, 'الفصل الصيفي'),
    ]

    section_id = models.IntegerField()
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='sections')
    instructor = models.ForeignKey(Instructor, on_delete=models.PROTECT, related_name='sections')
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='sections')
    semester = models.IntegerField(choices=SEMESTER_CHOICES)
    year = models.IntegerField()
    capacity = models.IntegerField()  # max students allowed in this section


    def __str__(self):
        return f"{self.subject.code} - {self.instructor} ({self.get_semester_display()} {self.year})"

    @property
    def is_full(self):
        return self.enrollments.count() >= self.capacity
    

class SectionSchedule(models.Model):
    DAYS_OF_WEEK = [
        ('ح', 'Sunday'),
        ('ن', 'Monday'),
        ('ث', 'Tuesday'),
        ('ر', 'Wednesday'),
        ('خ', 'Thursday'),
        ('ج', 'Friday'),
        ('س', 'Saturday'),
    ]

    section = models.ForeignKey(
        CourseSection,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    day = models.CharField(max_length=2, choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day', 'start_time']

    def __str__(self):
        return f"{self.day} {self.start_time} - {self.end_time}"
    
class ExamSchedule(models.Model):
    section = models.ForeignKey(
        CourseSection,
        on_delete=models.CASCADE,
        related_name='exam_schedules',
        blank=True,
        null=True
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='exam_schedules')
    mid = models.BooleanField(default=True)

    class Meta:
        unique_together = ('section', 'mid')  # one mid and one final per section

    def __str__(self):
        exam_type = 'نصفي' if self.mid else 'نهائي'
        return f"{self.section} — {exam_type} {self.date}"
    

class GradeDistribution(models.Model):
    SYMBOLS = [
        ('A',  'A',  4.00),
        ('A-', 'A-', 3.75),
        ('B+', 'B+', 3.50),
        ('B',  'B',  3.00),
        ('B-', 'B-', 2.75),
        ('C+', 'C+', 2.50),
        ('C',  'C',  2.00),
        ('C-', 'C-', 1.75),
        ('D+', 'D+', 1.50),
        ('D',  'D',  1.00),
        ('F*', 'F*', 0.50),
    ]

    SYMBOL_CHOICES = [(s[0], s[1]) for s in SYMBOLS]
    SYMBOL_POINTS  = {s[0]: s[2] for s in SYMBOLS}

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='grade_distributions'
    )
    semester = models.IntegerField(choices=[
        (1, 'الفصل الاول'),
        (2, 'الفصل الثاني'),
        (3, 'الفصل الصيفي'),
    ])
    year = models.IntegerField()
    symbol = models.CharField(max_length=5, choices=SYMBOL_CHOICES)
    min_grade = models.DecimalField(max_digits=5, decimal_places=2)  # e.g. 87.00
    max_grade = models.DecimalField(max_digits=5, decimal_places=2)  # e.g. 100.00

    class Meta:
        unique_together = ('subject', 'semester', 'year', 'symbol')
        ordering = ['-min_grade']

    def __str__(self):
        return f"{self.subject} {self.get_semester_display()} {self.year} — {self.symbol} ({self.min_grade}-{self.max_grade})"
class RegistrationPeriod(models.Model):
    semester = models.IntegerField(choices=[
        (1, 'First Semester'),
        (2, 'Second Semester'),
        (3, 'Summer Semester'),
    ])
    year = models.IntegerField()
    overall_start = models.DateField()
    overall_end = models.DateField()
    is_open = models.BooleanField(default=False)

    class Meta:
        unique_together = ('semester', 'year')

    def __str__(self):
        return f"{self.get_semester_display()} {self.year}"

    def get_window_for_student(self, student):
        """Returns the active window for a student based on their completed hours."""
        from django.utils import timezone
        now = timezone.now()
        completed = student.passed_hours + student.failed_hours

        return self.windows.filter(
            min_hours__lte=completed,
            max_hours__gte=completed,
            start_datetime__lte=now,
            end_datetime__gte=now
        ).first()


class RegistrationWindow(models.Model):
    period = models.ForeignKey(
        RegistrationPeriod,
        on_delete=models.CASCADE,
        related_name='windows'
    )
    min_hours = models.IntegerField()
    max_hours = models.IntegerField()
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    class Meta:
        ordering = ['min_hours', 'start_datetime']

    def __str__(self):
        return f"{self.period} — {self.min_hours} to {self.max_hours} hrs (starts {self.start_datetime}, ends {self.end_datetime})"


class SectionRequest(models.Model):
    STATUS = [
        ('pending', 'قيد الانتظار'),
        ('approved', 'مقبول'),
        ('rejected', 'مرفوض'),
    ]

    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='section_requests'
    )
    section = models.ForeignKey(
        CourseSection,
        on_delete=models.CASCADE,
        related_name='requests'
    )
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    handled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='handled_requests'
    )

    class Meta:
        unique_together = ('student', 'section')

    def __str__(self):
        return f"{self.student} — {self.section} ({self.get_status_display()})"