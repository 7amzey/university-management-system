from django.db import models

from apps.courses.constants import SUBJECT_TYPES

# Model for College it stores the name of the college and the head of the college which is an instructor
class College(models.Model):
    name = models.CharField(max_length=50)
    head = models.OneToOneField(
        'instructors.Instructor',  # string reference since instructors app exists
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_college'
    )

    def __str__(self):
        return self.name

# Model for department it stores the name of the department and the college it belongs to and the head of the department which is an instructor
class Department(models.Model):
    name = models.CharField(max_length=50)
    college = models.ForeignKey(College, on_delete=models.PROTECT, related_name='departments')
    head = models.OneToOneField(
        'instructors.Instructor',  # string reference
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_department'
    )

    def __str__(self):
        return f"{self.name} - {self.college.name}"


# Model for major it stores the name of the major and the department it belongs to and the total hours required for the major and the fee per hour for the major
class Major(models.Model):
    name = models.CharField(max_length=50)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='majors')
    hours = models.IntegerField()
    hour_fee = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.department.name})"
    

# Model for major subject requirement it stores the major, the subject type and the required hours for that subject type in that major
class MajorSubjectRequirement(models.Model):
    major = models.ForeignKey(Major, on_delete=models.CASCADE, related_name='subject_requirements')
    subject_type = models.CharField(max_length=30, choices=SUBJECT_TYPES)
    required_hours = models.IntegerField()

    class Meta:
        unique_together = ('major', 'subject_type')

    def __str__(self):
        return f"{self.major} — {self.subject_type}: {self.required_hours} hrs"