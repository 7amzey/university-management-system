from django.contrib import admin
from .models import Subject, CourseSection


class CourseSectionInline(admin.TabularInline):
    model = CourseSection
    extra = 1


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'department', 'hours')
    list_filter = ('department', 'majors')
    search_fields = ('name', 'code')
    inlines = [CourseSectionInline]


@admin.register(CourseSection)
class CourseSectionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'instructor', 'room', 'semester', 'year', 'capacity', 'is_full')
    list_filter = ('semester', 'year', 'subject__department')
    search_fields = ('subject__name', 'subject__code', 'instructor__first_name', 'instructor__last_name')