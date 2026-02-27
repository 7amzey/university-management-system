from django.contrib import admin
from .models import Student, Enrollment


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    readonly_fields = ('grade',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'first_name', 'last_name', 'college', 'major', 'degree', 'enrollment_year')
    list_filter = ('college', 'major', 'degree', 'study_type', 'acceptance_type', 'enrollment_year')
    search_fields = ('student_id', 'first_name', 'last_name', 'national_id')
    inlines = [EnrollmentInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'section', 'semester', 'year', 'mid_term_grade', 'participation_grade', 'final_term_grade', 'grade')
    list_filter = ('semester', 'year', 'section__subject__department')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')