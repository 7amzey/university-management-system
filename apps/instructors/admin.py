from django.contrib import admin
from .models import Instructor

@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'employee_id', 'college', 'department', 'rank')
    list_filter = ('college', 'department', 'rank')
    search_fields = ('first_name', 'last_name', 'employee_id', 'national_id')