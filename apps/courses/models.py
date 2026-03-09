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
        from students.models import Enrollment

        enrollments = list(
            Enrollment.objects.filter(
                section__subject=self,
                section__semester=semester,
                section__year=year,
                weighted_total__isnull=False
            ).order_by('-weighted_total')
        )

        total_students = len(enrollments)
        if total_students == 0:
            return

        distributions = GradeDistribution.objects.filter(
            subject=self,
            semester=semester,
            year=year
        ).order_by('-percentage')

        if not distributions.exists():
            return

        current_index = 0
        for dist in distributions:
            count = round(total_students * float(dist.percentage) / 100)
            points = GradeDistribution.SYMBOL_POINTS.get(dist.symbol, 0)

            for enrollment in enrollments[current_index:current_index + count]:
                enrollment.symbol = dist.symbol
                enrollment.grade_points = points
                enrollment.save()

            current_index += count

        # assign any remaining students the last symbol
        last_dist = distributions.last()
        last_points = GradeDistribution.SYMBOL_POINTS.get(last_dist.symbol, 0)
        for enrollment in enrollments[current_index:]:
            enrollment.symbol = last_dist.symbol
            enrollment.grade_points = last_points
            enrollment.save()


class CourseSection(models.Model):
    SEMESTER_CHOICES = [
        (1, 'الفصل الأول'),
        (2, 'الفصل الثاني'),
        (3, 'الفصل الصيفي'),
    ]

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
        return f"{self.get_day_display()} {self.start_time} - {self.end_time}"
    
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
    percentage = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ('subject', 'semester', 'year', 'symbol')
        ordering = ['-percentage']

    def __str__(self):
        return f"{self.subject} {self.get_semester_display()} {self.year} — {self.symbol} ({self.percentage}%)"