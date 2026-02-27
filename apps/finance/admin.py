from django.contrib import admin
from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('student', 'transaction_type', 'fee_type', 'amount', 'semester', 'year', 'is_system_generated', 'created_by', 'date')
    list_filter = ('transaction_type', 'fee_type', 'semester', 'year', 'is_system_generated')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    readonly_fields = ('date',)