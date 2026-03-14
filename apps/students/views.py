from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.students.models import Student, HourRegistration, Enrollment, absence
from apps.courses.models import Subject, CourseSection, ExamSchedule
from django.db.models import Sum, F
from django.db import models as db_models
from apps.courses.constants import SUBJECT_TYPES
from django.utils import timezone
from apps.announcements.models import Announcement



def student_login(request):
    if request.user.is_authenticated and request.session.get('is_student_portal'):
        return redirect('students:dashboard')

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        password = request.POST.get('password')

        user = authenticate(request, student_id=student_id, password=password)

        if user and user.role == 'student':
            login(request, user, backend='apps.accounts.backends.StudentBackend')
            request.session['is_student_portal'] = True
            return redirect('apps.students:dashboard')
        else:
            messages.error(request, 'Invalid student ID or password.')

    return render(request, 'students/login.html')


def student_logout(request):
    logout(request)
    return redirect('apps.students:login')


def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.session.get('is_student_portal'):
            return redirect('apps.students:login')
        if request.user.role != 'student':
            messages.error(request, 'Access denied.')
            return redirect('apps.students:login')
        return view_func(request, *args, **kwargs)
    return wrapper


@student_required
def dashboard(request):
    student = request.user.student_profile

    latest_reg = student.hour_registrations.order_by('-year', '-semester').first()
    current_enrollments = []
    midterm_exams = []
    final_exams = []

    absences = absence.objects.filter(enrollment__student=student)

    if latest_reg:
        current_enrollments = latest_reg.enrollments.select_related(
            'section__subject',
            'section__instructor',
            'section__room'
        )

        midterm_exams = ExamSchedule.objects.filter(
            section__in=[e.section for e in current_enrollments],
            mid=True
        ).select_related('section__subject', 'room').order_by('date', 'start_time')

        final_exams = ExamSchedule.objects.filter(
            section__in=[e.section for e in current_enrollments],
            mid=False
        ).select_related('section__subject', 'room').order_by('date', 'start_time')

    context = {
        'student': student,
        'gpa': student.gpa,
        'balance': student.balance,
        'latest_reg': latest_reg,
        'current_enrollments': current_enrollments,
        'midterm_exams': midterm_exams,
        'final_exams': final_exams,
        'absences': absences,
    }
    return render(request, 'students/dashboard.html', context)

@student_required
def finance(request):
    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()

    existing_reg = HourRegistration.objects.filter(
        student=student,
        semester=current_semester,
        year=current_year
    ).first()

    if request.method == 'POST':
        try:
            requested_hours = int(request.POST.get('requested_hours'))
            if requested_hours < student.min_hours or requested_hours > student.max_hours:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, f'الرجاء إدخال عدد ساعات بين {student.min_hours} و {student.max_hours}.')
            return redirect('apps.students:finance')

        if existing_reg:
            # check if value actually changed from current — not from paid
            if requested_hours == existing_reg.requested_hours:
                messages.info(request, 'لم تتغير الساعات.')
                return redirect('apps.students:finance')

            if existing_reg.is_paid:
                difference = requested_hours - existing_reg.paid_hours
                if difference > 0:
                    messages.success(request, f'تم زيادة الساعات إلى {requested_hours}، سيتم احتساب رسوم إضافية لـ {difference} ساعة.')
                elif difference < 0:
                    messages.success(request, f'تم تخفيض الساعات إلى {requested_hours}، سيتم استرداد رسوم {abs(difference)} ساعة.')
                else:
                    messages.success(request, f'تم إرجاع الساعات إلى {requested_hours}.')
            else:
                messages.success(request, f'تم تحديث تسجيل الساعات إلى {requested_hours} ساعة.')

            existing_reg.requested_hours = requested_hours
            existing_reg.save()

        else:
            HourRegistration.objects.create(
                student=student,
                semester=current_semester,
                year=current_year,
                requested_hours=requested_hours
            )
            messages.success(request, f'تم تسجيل {requested_hours} ساعة بنجاح.')

        return redirect('apps.students:finance')

    transactions = student.transactions.order_by('-date')

    pending = transactions.filter(
        transaction_type='charge',
        is_paid=False
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_payments = transactions.filter(
        transaction_type='payment',
        is_service=False
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'student': student,
        'transactions': transactions,
        'total_payments': total_payments,
        'pending': pending,
        'existing_reg': existing_reg,
        'current_semester': current_semester,
        'current_year': current_year,
    }
    return render(request, 'students/finance.html', context)

# students/views.py

def payment_lookup(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        try:
            student = Student.objects.get(student_id=student_id)
            return redirect('apps.students:payment_confirm', student_id=student_id)
        except Student.DoesNotExist:
            messages.error(request, 'رقم الطالب غير موجود.')
    return render(request, 'students/payment_lookup.html')


def payment_confirm(request, student_id):
    student = get_object_or_404(Student, student_id=student_id)
    current_year = timezone.now().year
    current_semester = get_current_semester()

    pending_transactions = student.transactions.filter(
        transaction_type='charge',
        is_paid=False
    )

    total_pending = pending_transactions.aggregate(
        total=Sum('amount'))['total'] or 0

    if request.method == 'POST':
        # mark all pending transactions as paid
        pending_transactions.update(is_paid=True, transaction_type='payment')

        # mark hour registration as paid
        HourRegistration.objects.filter(
            student=student,
            semester=current_semester,
            year=current_year,
            is_paid=False
        ).update(is_paid=True, paid_hours=F('requested_hours'))

        messages.success(request, f'تم استيفاء مبلغ {total_pending|floatformat:2} JD بنجاح.')
        return redirect('apps.students:payment_lookup')

    context = {
        'student': student,
        'pending_transactions': pending_transactions,
        'total_pending': total_pending,
    }
    return render(request, 'students/payment_confirm.html', context)


@student_required
def current_grades(request):
    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()

    current_reg = HourRegistration.objects.filter(
        student=student,
        semester=current_semester,
        year=current_year
    ).first()

    enrollments = []
    if current_reg:
        enrollments = current_reg.enrollments.select_related(
            'section__subject'
        ).order_by('section__subject__name')

    context = {
        'student': student,
        'enrollments': enrollments,
        'current_semester': current_reg.get_semester_display() if current_reg else '',
        'current_year': current_year,
    }
    return render(request, 'students/current_grades.html', context)


@student_required
def grade_history(request):
    student = request.user.student_profile

    # get all registrations ordered by year and semester
    registrations = student.hour_registrations.filter(
        is_paid=True
    ).order_by('-year', '-semester')

    semesters = []
    for reg in registrations:
        enrollments = reg.enrollments.filter(
            symbol__isnull=False
        ).select_related('section__subject')

        if not enrollments.exists():
            continue

        # semester gpa
        total_points = sum(
            e.grade_points * e.section.subject.hours
            for e in enrollments
            if e.grade_points is not None
        )
        total_hours = sum(
            e.section.subject.hours
            for e in enrollments
            if e.grade_points is not None
        )
        semester_gpa = round(total_points / total_hours, 2) if total_hours > 0 else None

        semesters.append({
            'reg': reg,
            'enrollments': enrollments,
            'semester_gpa': semester_gpa,
            'total_hours': total_hours,
        })

    context = {
        'student': student,
        'semesters': semesters,
        'cumulative_gpa': student.gpa,
    }
    return render(request, 'students/grade_history.html', context)

@student_required
def subject_catalog(request):
    student = request.user.student_profile

    subjects = Subject.objects.filter(
        majors=student.major
    ).prefetch_related('prerequisites').order_by('subject_type', 'code')

    passed_subject_ids = set(
        student.enrollments.filter(
            grade_points__isnull=False,
            grade_points__gt=0.5
        ).values_list('section__subject_id', flat=True)
    )

    enrolled_subject_ids = set(
        student.enrollments.filter(
            symbol__isnull=True
        ).values_list('section__subject_id', flat=True)
    )

    passed_enrollments = {
        e.section.subject_id: e.symbol
        for e in student.enrollments.filter(
            grade_points__isnull=False,
            grade_points__gt=0.5
        ).select_related('section__subject')
    }

    # fetch required hours per type for this major
    from apps.academics.models import MajorSubjectRequirement
    requirements = {
        r.subject_type: r.required_hours
        for r in MajorSubjectRequirement.objects.filter(major=student.major)
    }

    from collections import OrderedDict
    catalog = OrderedDict()
    for type_key, type_label in SUBJECT_TYPES:
        type_subjects = [s for s in subjects if s.subject_type == type_key]
        if type_subjects:
            total_hours = sum(s.hours for s in type_subjects)
            passed_hours = sum(s.hours for s in type_subjects if s.id in passed_subject_ids)
            required_hours = requirements.get(type_key)  # None if not set

            catalog[type_label] = {
                'subjects': type_subjects,
                'total_hours': total_hours,
                'passed_hours': passed_hours,
                'required_hours': required_hours,
            }

    # untyped = [s for s in subjects if not s.subject_type]
    # if untyped:
    #     catalog['غير مصنف'] = {
    #         'subjects': untyped,
    #         'total_hours': sum(s.hours for s in untyped),
    #         'passed_hours': sum(s.hours for s in untyped if s.id in passed_subject_ids),
    #         'required_hours': None,
    #     }

    context = {
        'student': student,
        'catalog': catalog,
        'passed_subject_ids': passed_subject_ids,
        'enrolled_subject_ids': enrolled_subject_ids,
        'passed_enrollments': passed_enrollments,
    }
    return render(request, 'students/subject_catalog.html', context)

@student_required
def announcements(request):
    student = request.user.student_profile
    last_seen = student.announcements_last_seen

    # fetch global + student-specific announcements
    student_announcements = Announcement.objects.filter(
        db_models.Q(student=student) | db_models.Q(student__isnull=True)
    ).order_by('-created_at')

    # update last seen to now so badge resets
    student.announcements_last_seen = timezone.now()
    student.save(update_fields=['announcements_last_seen'])

    context = {
        'announcements': student_announcements,
        'last_seen': last_seen,
    }
    return render(request, 'students/announcements.html', context)


@student_required
def profile(request):
    student = request.user.student_profile

    return render(request, 'students/profile.html', {'student': student})

@student_required
def drop_section(request, enrollment_id):
    student = request.user.student_profile
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, student=student)

    if enrollment.hour_registration.is_paid:
        # only allow drop if semester hasn't started — you can add a date check here later
        enrollment.delete()
        messages.success(request, f'Successfully dropped {enrollment.section.subject.name}.')
    else:
        messages.error(request, 'Cannot drop this course.')

    return redirect('apps.students:course_catalog')


def get_current_semester():
    """Returns current semester based on month."""
    month = timezone.now().month
    if 10 <= month <= 2:
        return 1  # First semester
    elif 2 <= month <= 6:
        return 2  # Second semester
    else:
        return 3  # Summer
