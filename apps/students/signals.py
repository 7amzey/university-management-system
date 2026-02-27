from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import HourRegistration

@receiver(post_save, sender=HourRegistration)
def charge_for_hours(sender, instance, created, **kwargs):
    from finance.models import Transaction
    fee_per_hour = 100

    if created:
        Transaction.objects.create(
            student=instance.student,
            transaction_type='charge',
            fee_type='semester',
            amount=instance.requested_hours * fee_per_hour,
            semester=instance.semester,
            year=instance.year,
            is_system_generated=True,
            created_by=None,
            note=f"Charged for {instance.requested_hours} registered hours"
        )
    else:
        # only update if not yet paid
        if not instance.is_paid:
            Transaction.objects.filter(
                student=instance.student,
                semester=instance.semester,
                year=instance.year,
                fee_type='semester',
                is_system_generated=True
            ).update(amount=instance.requested_hours * fee_per_hour,
                     note=f"Charged for {instance.requested_hours} registered hours")