# tickets/models.py
from django.db import models
from apps.students.models import Student

class Ticket(models.Model):
    CATEGORIES = [
        ('academic', 'أكاديمي'),
        ('financial', 'مالي'),
        ('technical', 'تقني'),
        ('other', 'أخرى'),
    ]

    STATUS = [
        ('open', 'مفتوح'),
        ('in_progress', 'قيد المعالجة'),
        ('closed', 'مغلق'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='tickets')
    category = models.CharField(max_length=20, choices=CATEGORIES)
    subject = models.CharField(max_length=100)
    status = models.CharField(max_length=15, choices=STATUS, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.student} — {self.subject} ({self.get_status_display()})"


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='ticket_messages')
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"{self.sender} — {self.ticket} ({self.sent_at})"