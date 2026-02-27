from django.db import models
from apps.academics.models import Department, Major
from apps.instructors.models import Instructor
from apps.facilities.models import Room


class Subject(models.Model):
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=10, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='subjects')
    majors = models.ManyToManyField(Major, related_name='subjects')
    hours = models.IntegerField()

    def __str__(self):
        return f"({self.code}) {self.name}"


class CourseSection(models.Model):
    SEMESTER_CHOICES = [
        (1, 'First Semester'),
        (2, 'Second Semester'),
        (3, 'Summer Semester'),
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