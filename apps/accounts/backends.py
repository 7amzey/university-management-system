from django.contrib.auth.backends import BaseBackend
from .models import User

# Custom authentication backends for students and instructors based on their id's (student_id and employee_id)
class StudentBackend(BaseBackend):
    def authenticate(self, request, student_id=None, password=None):
        try:
            user = User.objects.get(student_profile__student_id=student_id, role='student')
            if user.check_password(password) and user.is_active:
                return user
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class InstructorBackend(BaseBackend):
    def authenticate(self, request, employee_id=None, password=None):
        try:
            user = User.objects.get(instructor_profile__employee_id=employee_id, role='instructor')
            if user.check_password(password) and user.is_active:
                return user
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None