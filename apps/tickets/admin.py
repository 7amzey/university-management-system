from django.contrib import admin
from .models import Ticket, TicketMessage

# Register your models here.

class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 1
    readonly_fields = ('sender', 'sent_at')
    fields = ('sender', 'body', 'sent_at')

    def get_extra(self, request, obj=None, **kwargs):
        return 1 if obj else 0

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('student', 'category', 'subject', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'category')
    search_fields = ('student__first_name', 'student__student_id', 'subject')
    readonly_fields = ('student', 'category', 'subject', 'created_at')
    inlines = [TicketMessageInline]

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, TicketMessage) and not instance.pk:
                instance.sender = request.user
                instance.save()
        formset.save_m2m()