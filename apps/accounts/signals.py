from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User
from apps.students.models import Student
from apps.instructors.models import Instructor


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == 'student':
            Student.objects.create(user=instance)
        elif instance.role == 'instructor':
            Instructor.objects.create(user=instance)