from django.contrib import admin
from .models import SectionSchedule, Subject, CourseSection, GradeDistribution, RegistrationPeriod, RegistrationWindow, SectionRequest
from apps.students.views import get_current_semester

class GradeDistributionInline(admin.TabularInline):
    model = GradeDistribution
    extra = 11
    fields = ('symbol', 'min_grade', 'max_grade', 'semester', 'year')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'subject_type', 'department', 'hours')
    list_filter = ('subject_type', 'department', 'majors')
    search_fields = ('name', 'code')
    filter_horizontal = ('majors', 'prerequisites')  # nice UI for ManyToMany
    inlines = [GradeDistributionInline]

class SectionScheduleInline(admin.TabularInline):
    model = SectionSchedule
    extra = 3
    fields = ('day', 'start_time', 'end_time')

@admin.register(CourseSection)
class CourseSectionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'instructor', 'room', 'semester', 'year', 'capacity')
    list_filter = ('semester', 'year', 'subject__department')
    search_fields = ('subject__name', 'subject__code')
    actions = ['assign_symbols']
    inlines = [SectionScheduleInline]

    @admin.action(description='Assign symbols based on grade distribution')
    def assign_symbols(self, request, queryset):
        processed = set()
        for section in queryset:
            key = (section.subject_id, section.semester, section.year)
            if key not in processed:
                section.subject.assign_symbols(section.semester, section.year)
                processed.add(key)
        self.message_user(request, 'تم توزيع الرموز بنجاح.')

class RegistrationWindowInline(admin.TabularInline):
    model = RegistrationWindow
    extra = 3
    fields = ('min_hours', 'max_hours', 'start_datetime', 'end_datetime')


@admin.register(RegistrationPeriod)
class RegistrationPeriodAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'overall_start', 'overall_end', 'is_open')
    inlines = [RegistrationWindowInline]
    actions = ['open_registration', 'close_registration']

    @admin.action(description='Open registration')
    def open_registration(self, request, queryset):
        queryset.update(is_open=True)

    @admin.action(description='Close registration')
    def close_registration(self, request, queryset):
        queryset.update(is_open=False)


@admin.register(SectionRequest)
class SectionRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'section', 'status', 'created_at', 'handled_by')
    list_filter = ('status', 'section__semester', 'section__year')
    search_fields = ('student__first_name', 'student__student_id', 'section__subject__name')
    actions = ['approve_requests', 'reject_requests']

    @admin.action(description='Approve selected requests')
    def approve_requests(self, request, queryset):
        for req in queryset:
            req.status = 'approved'
            req.handled_by = request.user
            req.save()
            # enroll the student directly
            from students.models import HourRegistration, Enrollment
            from django.utils import timezone
            current_year = timezone.now().year
            current_semester = get_current_semester()
            reg = HourRegistration.objects.filter(
                student=req.student,
                semester=current_semester,
                year=current_year,
                is_paid=True
            ).first()
            if reg:
                Enrollment.objects.get_or_create(
                    student=req.student,
                    section=req.section,
                    defaults={'hour_registration': reg}
                )
                # notify student
                from announcements.models import Announcement
                Announcement.objects.create(
                    student=req.student,
                    trigger_type='custom',
                    title='تم قبول طلب فتح الشعبة',
                    body=f'تم قبول طلبك لتسجيل شعبة {req.section.subject.name} وتم تسجيلك فيها.'
                )
        self.message_user(request, 'تم قبول الطلبات المحددة وتسجيل الطلاب.')

    @admin.action(description='Reject selected requests')
    def reject_requests(self, request, queryset):
        for req in queryset:
            req.status = 'rejected'
            req.handled_by = request.user
            req.save()
            from announcements.models import Announcement
            Announcement.objects.create(
                student=req.student,
                trigger_type='custom',
                title='تم رفض طلب فتح الشعبة',
                body=f'تم رفض طلبك لفتح شعبة {req.section.subject.name}.'
            )
        self.message_user(request, 'تم رفض الطلبات المحددة.')

@admin.register(SectionSchedule)
class SectionScheduleAdmin(admin.ModelAdmin):
    list_display = ('section', 'day', 'start_time', 'end_time')
    list_filter = ('section__semester', 'section__year', 'day')
    search_fields = ('section__subject__name',)


@admin.register(GradeDistribution)
class GradeDistributionAdmin(admin.ModelAdmin):
    list_display = ('subject', 'semester', 'year', 'symbol', 'min_grade', 'max_grade')
    list_filter = ('semester', 'year', 'subject__department')
    search_fields = ('subject__name', 'subject__code')
    ordering = ('subject', 'semester', 'year', '-min_grade')