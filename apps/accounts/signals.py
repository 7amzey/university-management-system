from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == 'student':
            from apps.students.models import Student
            Student.objects.create(user=instance)
        elif instance.role == 'instructor':
            from apps.instructors.models import Instructor
            Instructor.objects.create(user=instance)