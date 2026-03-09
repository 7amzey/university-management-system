from django.contrib import admin
from .models import Student, Enrollment, HourRegistration, absence


# class EnrollmentInline(admin.TabularInline):
#     model = Enrollment
#     extra = 0
#     readonly_fields = ('grade',)

class HourRegistrationInline(admin.TabularInline):
    model = HourRegistration
    extra = 0
    readonly_fields = ('is_paid',)  # staff shouldn't change this from the student page, only from HourRegistration page

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'first_name', 'last_name', 'college', 'major', 'degree', 'enrollment_year')
    list_filter = ('college', 'major', 'degree', 'study_type', 'acceptance_type', 'enrollment_year')
    search_fields = ('student_id', 'first_name', 'last_name', 'national_id')
    # inlines = [EnrollmentInline]

@admin.register(HourRegistration)
class HourRegistrationAdmin(admin.ModelAdmin):
    list_display = ('student', 'semester', 'year', 'requested_hours', 'paid_hours', 'is_paid')
    actions = ['mark_as_paid']

    @admin.action(description='Mark selected registrations as paid')
    def mark_as_paid(self, request, queryset):
        for reg in queryset:
            reg.is_paid = True
            reg.paid_hours = reg.requested_hours  # lock in what was paid
            reg.save()

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'section', 'mid_term_grade', 'participation_grade', 'final_term_grade', 'weighted_total', 'symbol', 'grade_points')
    list_filter = ('section__semester', 'section__year', 'section__subject__department')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    readonly_fields = ('weighted_total', 'symbol', 'grade_points')
    
@admin.register(absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'count')
    search_fields = ('enrollment__student__first_name', 'enrollment__student__last_name', 'enrollment__student__student_id')
