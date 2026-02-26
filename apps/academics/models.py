# academics/models.py
from django.db import models

class College(models.Model):
    name = models.CharField(max_length=50)
    # head will be added after teachers app is created

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=50)
    college = models.ForeignKey(College, on_delete=models.PROTECT, related_name='departments')
    # head will be added after teachers app is created

    def __str__(self):
        return f"{self.name} - {self.college.name}"


class Major(models.Model):
    name = models.CharField(max_length=50)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='majors')
    hours = models.IntegerField()

    def __str__(self):
        return f"{self.name} ({self.department.name})"