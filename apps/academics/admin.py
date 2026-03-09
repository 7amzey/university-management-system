from django.contrib import admin
from .models import College, Department, Major, MajorSubjectRequirement

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

class MajorSubjectRequirementInline(admin.TabularInline):
    model = MajorSubjectRequirement
    extra = 6
    fields = ('subject_type', 'required_hours')

@admin.register(Major)
class MajorAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'hours')
    inlines = [MajorSubjectRequirementInline]