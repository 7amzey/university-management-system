from django.contrib import admin
from .models import Subject, CourseSection, GradeDistribution

class GradeDistributionInline(admin.TabularInline):
    model = GradeDistribution
    extra = 11
    fields = ('symbol', 'percentage')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'subject_type', 'department', 'hours')
    list_filter = ('subject_type', 'department', 'majors')
    search_fields = ('name', 'code')
    filter_horizontal = ('majors', 'prerequisites')  # nice UI for ManyToMany
    inlines = [GradeDistributionInline]


@admin.register(CourseSection)
class CourseSectionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'instructor', 'room', 'semester', 'year', 'capacity')
    list_filter = ('semester', 'year', 'subject__department')
    search_fields = ('subject__name', 'subject__code')
    actions = ['assign_symbols']

    @admin.action(description='Assign symbols based on grade distribution')
    def assign_symbols(self, request, queryset):
        processed = set()
        for section in queryset:
            key = (section.subject_id, section.semester, section.year)
            if key not in processed:
                section.subject.assign_symbols(section.semester, section.year)
                processed.add(key)
        self.message_user(request, 'تم توزيع الرموز بنجاح.')