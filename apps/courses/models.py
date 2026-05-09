from django.db import models
from apps.academics.models import Department, Major
from apps.instructors.models import Instructor
from apps.facilities.models import Room
from .constants import SUBJECT_TYPES, DAYS_OF_WEEK, SYMBOLS, SEMESTER_CHOICES, STATUS
from django.core.validators import MinValueValidator


"""
    Subject model represents an academic subject/course offered by the university.
    It includes details like name, code, type, department, associated majors, credit hours, and prerequisites.
    It also has a method to assign grade symbols to students based on their performance in a given semester and year.
"""

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
    
    # This method calculates and assigns grade symbols to students enrolled in this subject for a specific semester and year.
    def assign_symbols(self, semester, year):
        from apps.students.models import Enrollment

        enrollments = Enrollment.objects.filter(
            section__subject=self,
            section__semester=semester,
            section__year=year,
            weighted_total__isnull=False,
            status='active'
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


# CourseSection model represents a specific offering of a subject in a given semester and year.
class CourseSection(models.Model):
    SEMESTER_CHOICES = [
        (1, 'الفصل الأول'),
        (2, 'الفصل الثاني'),
        (3, 'الفصل الصيفي'),
    ]

    section_id = models.IntegerField(validators=[
        MinValueValidator(1),
    ])
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='sections')
    semester = models.IntegerField(choices=SEMESTER_CHOICES)
    year = models.IntegerField()
    capacity = models.IntegerField()  # max students allowed in this section


    def __str__(self):
        return f"{self.subject.name}"

    # This property checks if the section has reached its maximum capacity based on the number of enrollments.
    @property
    def is_full(self):
        return self.enrollments.count() >= self.capacity
    
    # This property retrieves the instructors teaching this section by looking up the related schedules and extracting the distinct instructors.
    @property
    def instructors(self):
        return Instructor.objects.filter(
            schedules__section=self
        ).distinct()
    
    # This property retrieves the rooms assigned to this section by looking up the related schedules and extracting the distinct rooms.
    @property
    def rooms(self):
        from apps.facilities.models import Room
        return Room.objects.filter(schedules__section=self).distinct()


# SectionSchedule model represents the schedule for a specific course section, including the day of the week, start and end times, assigned instructor, and room.
class SectionSchedule(models.Model):
    section = models.ForeignKey(
        CourseSection,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    instructor = models.ForeignKey(
        'instructors.Instructor',
        on_delete=models.PROTECT,
        related_name='schedules',
        null=True, blank=True
    )
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='schedules', null=True, blank=True)
    day = models.IntegerField(max_length=2, choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day', 'start_time']

    def __str__(self):
        return f"{self.get_day_display()} {self.start_time} - {self.end_time}"
    

# ExamSchedule model represents the schedule for exams (midterm and final) for a specific course section, including the date, time, assigned rooms, and whether it's a midterm or final exam.
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
    room = models.ManyToManyField(Room, related_name='exam_schedules')
    mid = models.BooleanField(default=True)

    class Meta:
        unique_together = ('section', 'mid')  # one mid and one final per section

    def __str__(self):
        exam_type = 'نصفي' if self.mid else 'نهائي'
        return f"{self.section} — {exam_type} {self.date}"
    

# GradeDistribution model represents the mapping of grade symbols (like A, B+, etc.) to the minimum and maximum grade percentages for a specific subject in a given semester and year. This allows the system to assign letter grades to students based on their performance.
class GradeDistribution(models.Model):
    SYMBOL_CHOICES = [(s[0], s[1]) for s in SYMBOLS]
    SYMBOL_POINTS  = {s[0]: s[2] for s in SYMBOLS}

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='grade_distributions'
    )
    semester = models.IntegerField(choices=SEMESTER_CHOICES)
    year = models.IntegerField()
    symbol = models.CharField(max_length=5, choices=SYMBOL_CHOICES)
    min_grade = models.DecimalField(max_digits=5, decimal_places=2)  # e.g. 87.00
    max_grade = models.DecimalField(max_digits=5, decimal_places=2)  # e.g. 100.00

    class Meta:
        unique_together = ('subject', 'semester', 'year', 'symbol')
        ordering = ['-min_grade']

    def __str__(self):
        return f"{self.subject} {self.get_semester_display()} {self.year} — {self.symbol} ({self.min_grade}-{self.max_grade})"


"""
    RegistrationPeriod model represents the registration period for a specific semester and year, including the overall start and end dates for registration and whether the registration is currently open.
    It also has a method to determine the active registration window for a student based on their completed hours.
"""
class RegistrationPeriod(models.Model):
    semester = models.IntegerField(choices=SEMESTER_CHOICES)
    year = models.IntegerField()
    overall_start = models.DateField()
    overall_end = models.DateField()
    is_open = models.BooleanField(default=False)

    class Meta:
        unique_together = ('semester', 'year')

    def __str__(self):
        return f"{self.get_semester_display()} {self.year}"


    """Returns the active window for a student based on their completed hours."""
    def get_window_for_student(self, student):
        from django.utils import timezone
        now = timezone.now()
        completed = student.passed_hours + student.failed_hours

        return self.windows.filter(
            min_hours__lte=completed,
            max_hours__gte=completed,
            start_datetime__lte=now,
            end_datetime__gte=now
        ).first()



# RegistrationWindow model represents a specific registration window within a registration period, defined by the minimum and maximum completed hours for students, as well as the start and end datetimes for that window.
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


# SectionRequest model represents a student's request to enroll in a specific course section, including the status of the request (pending, approved, rejected), the date it was created, any notes from the student, and the staff member who handled the request.
class SectionRequest(models.Model):
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