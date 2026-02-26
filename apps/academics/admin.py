from django.contrib import admin
from .models import College, Department, Major

class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 1

class MajorInline(admin.TabularInline):
    model = Major
    extra = 1

@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines = [DepartmentInline]

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'college',)
    list_filter = ('college',)
    inlines = [MajorInline]

@admin.register(Major)
class MajorAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'hours')
    list_filter = ('department__college', 'department')