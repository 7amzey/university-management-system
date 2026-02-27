from django.contrib import admin
from .models import Student, Enrollment, HourRegistration


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    readonly_fields = ('grade',)

class HourRegistrationInline(admin.TabularInline):
    model = HourRegistration
    extra = 0
    readonly_fields = ('is_paid',)  # staff shouldn't change this from the student page, only from HourRegistration page

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'first_name', 'last_name', 'college', 'major', 'degree', 'enrollment_year')
    list_filter = ('college', 'major', 'degree', 'study_type', 'acceptance_type', 'enrollment_year')
    search_fields = ('student_id', 'first_name', 'last_name', 'national_id')
    inlines = [EnrollmentInline]

@admin.register(HourRegistration)
class HourRegistrationAdmin(admin.ModelAdmin):
    list_display = ('student', 'semester', 'year', 'requested_hours', 'is_paid')
    list_filter = ('semester', 'year', 'is_paid')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    readonly_fields = ('student', 'semester', 'year', 'requested_hours')  # staff can only change is_paid, not the registration details
    actions = ['mark_as_paid']

    @admin.action(description='Mark selected registrations as paid')
    def mark_as_paid(self, request, queryset):
        queryset.update(is_paid=True)

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'section', 'get_semester', 'get_year', 'mid_term_grade', 'participation_grade', 'final_term_grade', 'grade')
    list_filter = ('hour_registration__semester', 'hour_registration__year', 'section__subject__department')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')

    @admin.display(description='Semester')
    def get_semester(self, obj):
        return obj.hour_registration.get_semester_display()

    @admin.display(description='Year')
    def get_year(self, obj):
        return obj.hour_registration.year