from django.contrib import admin
from .models import Announcement

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'trigger_type', 'student', 'created_at', 'created_by')
    list_filter = ('trigger_type', 'created_at')
    search_fields = ('title', 'body', 'student__first_name', 'student__student_id')
    raw_id_fields = ('student',)  # avoids loading all students in a dropdown

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # only on creation
            obj.created_by = request.user
            obj.trigger_type = 'custom'
        super().save_model(request, obj, form, change)