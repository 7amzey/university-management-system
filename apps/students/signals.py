# students/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import HourRegistration

@receiver(post_save, sender=HourRegistration, dispatch_uid='handle_hour_registration')
def handle_hour_registration(sender, instance, created, **kwargs):
    from apps.finance.models import Transaction
    fee_per_hour = instance.student.major.hour_fee

    if created:
        Transaction.objects.create(
            student=instance.student,
            transaction_type='charge',
            fee_type='semester',
            amount=instance.requested_hours * fee_per_hour,
            semester=instance.semester,
            year=instance.year,
            is_system_generated=True,
            note=f"رسوم تسجيل {instance.requested_hours} ساعة"
        )

    else:
        if not instance.is_paid:
            # before payment — always update the single existing charge
            Transaction.objects.filter(
                student=instance.student,
                semester=instance.semester,
                year=instance.year,
                fee_type='semester',
                is_system_generated=True,
                is_paid=False
            ).update(
                amount=instance.requested_hours * fee_per_hour,
                note=f"رسوم تسجيل {instance.requested_hours} ساعة"
            )

        else:
            difference = instance.requested_hours - instance.paid_hours

            # always clean up any existing unpaid charge first
            Transaction.objects.filter(
                student=instance.student,
                semester=instance.semester,
                year=instance.year,
                fee_type='semester',
                is_system_generated=True,
                is_paid=False,
                transaction_type='charge'
            ).delete()

            # always clean up any existing refund first
            Transaction.objects.filter(
                student=instance.student,
                semester=instance.semester,
                year=instance.year,
                fee_type='semester',
                is_system_generated=True,
                transaction_type='refund'
            ).delete()

            if difference > 0:
                # above paid hours — create a fresh charge for the difference
                Transaction.objects.create(
                    student=instance.student,
                    transaction_type='charge',
                    fee_type='semester',
                    amount=difference * fee_per_hour,
                    semester=instance.semester,
                    year=instance.year,
                    is_system_generated=True,
                    note=f"رسوم إضافية لزيادة {difference} ساعة عن الساعات المدفوعة"
                )

            elif difference < 0:
                # below paid hours — create a fresh refund for the difference
                Transaction.objects.create(
                    student=instance.student,
                    transaction_type='refund',
                    fee_type='semester',
                    amount=abs(difference) * fee_per_hour,
                    semester=instance.semester,
                    year=instance.year,
                    is_system_generated=True,
                    note=f"استرداد رسوم تخفيض {abs(difference)} ساعة"
                )