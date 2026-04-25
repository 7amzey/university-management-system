from urllib import request

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.students.models import Student, HourRegistration, Enrollment, absence
from apps.courses.models import SectionSchedule, Subject, CourseSection, ExamSchedule, RegistrationPeriod, SectionRequest
from django.db.models import Count, Sum, F
from django.db import models as db_models
from apps.courses.constants import SUBJECT_TYPES
from django.utils import timezone
from apps.announcements.models import Announcement
from apps.tickets.models import Ticket, TicketMessage

from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from .pdf_utils import ar, ar_style



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

    DAY_MAP = {6: 'ح', 0: 'ن', 1: 'ث', 2: 'ر', 3: 'خ', 4: 'ج', 5: 'س'}
    today_day = DAY_MAP.get(timezone.now().weekday())
    today_schedules = []

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

        today_schedules = SectionSchedule.objects.filter(
            section__in=[e.section for e in current_enrollments],
            day=today_day
        ).select_related(
            'section__subject',
            'section__instructor',
            'section__room'
        ).order_by('start_time')

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
        'today_schedules': today_schedules,
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

        messages.success(request, f'تم استيفاء مبلغ {round(total_pending, 2)} JD بنجاح.')
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


def get_pending_sections(request):
    return request.session.get('pending_sections', {})

def set_pending_sections(request, pending):
    request.session['pending_sections'] = pending
    request.session.modified = True

def clear_pending_sections(request):
    request.session.pop('pending_sections', None)
    request.session.modified = True

def get_pending_drops(request):
    return request.session.get('pending_drops', [])

def set_pending_drops(request, drops):
    request.session['pending_drops'] = drops
    request.session.modified = True

def get_eligible_subjects(student, semester, year):
    """Subjects the student can enroll in this semester."""
    from django.db.models import Q

    # subjects in major plan
    major_subjects = Subject.objects.filter(
        majors=student.major
    ).prefetch_related('prerequisites')

    # subjects already passed (grade_points > 1.75 means above C-)
    passed_ids = set(
        student.enrollments.filter(
            grade_points__gt=1.75
        ).values_list('section__subject_id', flat=True)
    )

    eligible = []
    for subject in major_subjects:
        # skip already passed
        if subject.id in passed_ids:
            continue

        # check prerequisites
        prereqs_met = all(
            p.id in passed_ids
            for p in subject.prerequisites.all()
        )
        if not prereqs_met:
            continue

        eligible.append(subject)

    return eligible


@student_required
def course_catalog(request):
    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()

    period = RegistrationPeriod.objects.filter(
        semester=current_semester,
        year=current_year,
        is_open=True
    ).first()

    window = period.get_window_for_student(student) if period else None

    student_windows = period.windows.filter(
        min_hours__lte=student.passed_hours + student.failed_hours,
        max_hours__gte=student.passed_hours + student.failed_hours
    ).order_by('start_datetime') if period else None

    hour_reg = HourRegistration.objects.filter(
        student=student,
        semester=current_semester,
        year=current_year,
        is_paid=True
    ).first()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'drop_confirmed':
            enrollment_id = request.POST.get('enrollment_id')
            pending_drops = get_pending_drops(request)
            if enrollment_id not in pending_drops:
                pending_drops.append(enrollment_id)
                set_pending_drops(request, pending_drops)
        return redirect('apps.students:course_catalog')

    # everything below is GET only
    pending_dict = get_pending_sections(request)
    pending_drops = get_pending_drops(request)

    confirmed_enrollments = []
    pending_sections = []
    confirmed_subject_ids = set()
    confirmed_hours = 0
    pending_hours = 0
    eligible_subjects = []
    pending_subject_ids = set()

    confirmed_enrollments = Enrollment.objects.filter(
        hour_registration=hour_reg
    ).select_related('section__subject', 'section__room', 'section__instructor')

    confirmed_subject_ids = set(e.section.subject_id for e in confirmed_enrollments)
    confirmed_hours = sum(
        e.section.subject.hours for e in confirmed_enrollments
        if str(e.id) not in pending_drops
    )

    if period and window and hour_reg:
        if pending_dict:
            pending_sections = list(
                CourseSection.objects.filter(
                    id__in=pending_dict.values()
                ).select_related('subject', 'room', 'instructor')
            )

        pending_hours = sum(s.subject.hours for s in pending_sections)
        pending_subject_ids = {int(k) for k in pending_dict.keys()}

        eligible_subjects = [
            s for s in get_eligible_subjects(student, current_semester, current_year)
            if CourseSection.objects.filter(
                subject=s,
                semester=current_semester,
                year=current_year
            ).exists()
        ]

    # build unified schedule — skip pending drops
    schedule = []
    for enrollment in confirmed_enrollments:
        if str(enrollment.id) in pending_drops:
            continue
        schedule.append({
            'subject_code': enrollment.section.subject.code,
            'subject_name': enrollment.section.subject.name,
            'subject_hours': enrollment.section.subject.hours,
            'subject_id': enrollment.section.subject_id,
            'section_id': enrollment.section_id,
            'schedules': enrollment.section.schedules.all(),
            'instructor': enrollment.section.instructor,
            'room': enrollment.section.room,
            'status': 'confirmed',
            'enrollment_id': enrollment.id,
        })

    for section in pending_sections:
        schedule.append({
            'subject_code': section.subject.code,
            'subject_name': section.subject.name,
            'subject_hours': section.subject.hours,
            'subject_id': section.subject_id,
            'section_id': section.id,
            'schedules': section.schedules.all(),
            'instructor': section.instructor,
            'room': section.room,
            'status': 'pending',
            'enrollment_id': None,
        })

    context = {
        'student': student,
        'period': period,
        'window': window,
        'hour_reg': hour_reg,
        'schedule': schedule,
        'student_windows': student_windows,
        'pending_sections': pending_sections,
        'confirmed_hours': confirmed_hours,
        'pending_hours': pending_hours,
        'total_hours': confirmed_hours + pending_hours,
        'eligible_subjects': eligible_subjects,
        'confirmed_subject_ids': confirmed_subject_ids,
        'pending_subject_ids': pending_subject_ids,
        'current_semester': current_semester,
        'current_year': current_year,
    }
    return render(request, 'students/course_catalog.html', context)

@student_required
def subject_sections(request, subject_id):
    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()

    subject = get_object_or_404(Subject, id=subject_id)

    hour_reg = HourRegistration.objects.filter(
        student=student,
        semester=current_semester,
        year=current_year,
        is_paid=True
    ).first()

    if not hour_reg:
        messages.error(request, 'يجب دفع رسوم تسجيل الساعات أولاً.')
        return redirect('apps.students:finance')

    sections = CourseSection.objects.filter(
        subject=subject,
        semester=current_semester,
        year=current_year
    ).prefetch_related('schedules').select_related(
        'instructor', 'room'
    ).annotate(confirmed_count=Count('enrollments'))

    confirmed_enrollment = Enrollment.objects.filter(
        student=student,
        section__subject=subject,
        section__semester=current_semester,
        section__year=current_year
    ).first()

    pending_dict = get_pending_sections(request)
    pending_section_id = pending_dict.get(str(subject_id))

    requested_section_ids = set(
        SectionRequest.objects.filter(
            student=student,
            section__subject=subject,
            status='pending'
        ).values_list('section_id', flat=True)
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        section_id = int(request.POST.get('section_id'))
        section = get_object_or_404(CourseSection, id=section_id)

        if action == 'enroll':
            if section.enrollments.count() >= section.capacity:
                messages.error(request, 'هذه الشعبة ممتلئة.')
                return redirect('apps.students:subject_sections', subject_id=subject_id)

            new_schedules = list(section.schedules.all())
            conflict = False
            conflict_subject = ''

            for enrollment in Enrollment.objects.filter(
                hour_registration=hour_reg
            ).exclude(section__subject=subject).prefetch_related('section__schedules'):
                for es in enrollment.section.schedules.all():
                    for ns in new_schedules:
                        if (es.day == ns.day and
                            es.start_time < ns.end_time and
                            ns.start_time < es.end_time):
                            conflict = True
                            conflict_subject = enrollment.section.subject.name
                            break

            if not conflict:
                other_pending_ids = [
                    sid for subj_id, sid in pending_dict.items()
                    if int(subj_id) != subject_id
                ]
                for ps in CourseSection.objects.filter(
                    id__in=other_pending_ids
                ).prefetch_related('schedules'):
                    for es in ps.schedules.all():
                        for ns in new_schedules:
                            if (es.day == ns.day and
                                es.start_time < ns.end_time and
                                ns.start_time < es.end_time):
                                conflict = True
                                conflict_subject = ps.subject.name
                                break

            if conflict:
                messages.error(request, f'يوجد تعارض في الجدول مع مادة {conflict_subject}.')
                return redirect('apps.students:subject_sections', subject_id=subject_id)

            pending_dict[str(subject_id)] = section_id
            set_pending_sections(request, pending_dict)
            messages.success(request, f'تمت إضافة {subject.name} إلى جدولك المؤقت.')

        elif action == 'remove_pending':
            pending_dict.pop(str(subject_id), None)
            set_pending_sections(request, pending_dict)
            messages.success(request, f'تمت إزالة {subject.name} من جدولك المؤقت.')

        elif action == 'request':
            if section.enrollments.count() < section.capacity:
                messages.error(request, 'هذه الشعبة لم تمتلئ بعد.')
                return redirect('apps.students:subject_sections', subject_id=subject_id)

            SectionRequest.objects.get_or_create(
                student=student,
                section=section,
                defaults={'status': 'pending'}
            )
            from announcements.models import Announcement
            Announcement.objects.create(
                student=None,
                trigger_type='custom',
                title='طلب فتح شعبة',
                body=f'الطالب {student.full_name_ar} ({student.student_id}) يطلب فتح شعبة {section.subject.name}.'
            )
            messages.success(request, 'تم إرسال طلب فتح الشعبة.')

        return redirect('apps.students:subject_sections', subject_id=subject_id)

    context = {
        'subject': subject,
        'sections': sections,
        'confirmed_enrollment': confirmed_enrollment,
        'pending_section_id': pending_section_id,
        'requested_section_ids': requested_section_ids,
    }
    return render(request, 'students/subject_sections.html', context)

@student_required
def submit_enrollment(request):
    if request.method != 'POST':
        return redirect('apps.students:course_catalog')

    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()

    hour_reg = HourRegistration.objects.filter(
        student=student,
        semester=current_semester,
        year=current_year,
        is_paid=True
    ).first()

    if not hour_reg:
        messages.error(request, 'يجب دفع رسوم تسجيل الساعات أولاً.')
        return redirect('apps.students:finance')

    pending_dict = get_pending_sections(request)
    if not pending_dict:
        messages.error(request, 'لا توجد مواد معلقة للتأكيد.')
        return redirect('apps.students:course_catalog')

    pending_sections = list(
        CourseSection.objects.filter(
            id__in=pending_dict.values()
        ).select_related('subject')
    )

    confirmed_hours = Enrollment.objects.filter(
        hour_registration=hour_reg
    ).aggregate(
        total=Sum('section__subject__hours')
    )['total'] or 0

    pending_hours = sum(s.subject.hours for s in pending_sections)
    total_hours = confirmed_hours + pending_hours

    if total_hours < student.min_hours:
        messages.error(
            request,
            f'مجموع الساعات ({total_hours}) أقل من الحد الأدنى ({student.min_hours} ساعة).'
        )
        return redirect('apps.students:course_catalog')

    if total_hours > hour_reg.requested_hours:
        messages.error(
            request,
            f'مجموع الساعات ({total_hours}) يتجاوز الساعات المسجلة ({hour_reg.requested_hours} ساعة).'
        )
        return redirect('apps.students:course_catalog')

    # single bulk write to DB
    for section in pending_sections:
        # if student already has a confirmed enrollment for this subject, replace it
        existing = Enrollment.objects.filter(
            student=student,
            section__subject=section.subject,
            section__semester=current_semester,
            section__year=current_year
        ).first()

        if existing:
            existing.section = section
            existing.save()
        else:
            Enrollment.objects.create(
                student=student,
                section=section,
                hour_registration=hour_reg
            )
    
    pending_drops = get_pending_drops(request)
    if pending_drops:
        Enrollment.objects.filter(id__in=pending_drops, student=student).delete()

    clear_pending_sections(request)
    set_pending_drops(request, [])
    messages.success(request, f'تم تأكيد تسجيل {len(pending_sections)} مادة بنجاح.')
    return redirect('apps.students:course_catalog')

@student_required
def drop_section(request, enrollment_id):
    student = request.user.student_profile
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, student=student)
    name = enrollment.section.subject.name
    enrollment.delete()
    messages.success(request, f'تم حذف {name} من جدولك.')
    return redirect('apps.students:course_catalog')

@student_required
def services(request):
    return render(request, 'students/services.html')

@student_required
def submit_ticket(request):
    if request.method != 'POST':
        return redirect('apps.students:dashboard')

    student = request.user.student_profile
    category = request.POST.get('category')
    subject = request.POST.get('subject', '').strip()
    body = request.POST.get('body', '').strip()

    if not subject or not body or not category:
        return HttpResponse(status=400)

    ticket = Ticket.objects.create(
        student=student,
        category=category,
        subject=subject,
    )
    TicketMessage.objects.create(
        ticket=ticket,
        sender=request.user,
        body=body
    )
    return HttpResponse(status=200)


@student_required
def tickets_list(request):
    student = request.user.student_profile
    tickets = student.tickets.all()
    context = {
        'tickets': tickets,
    }
    return render(request, 'students/tickets_list.html', context)


@student_required
def ticket_detail(request, ticket_id):
    student = request.user.student_profile
    ticket = get_object_or_404(Ticket, id=ticket_id, student=student)
    messages_list = ticket.messages.select_related('sender')

    if request.method == 'POST':
        if ticket.status == 'closed':
            messages.error(request, 'هذه التذكرة مغلقة ولا يمكن الرد عليها.')
            return redirect('apps.students:ticket_detail', ticket_id=ticket_id)

        body = request.POST.get('body', '').strip()
        if body:
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                body=body
            )
            # reopen ticket if it was in_progress
            if ticket.status != 'open':
                ticket.status = 'open'
                ticket.save()

        return redirect('apps.students:ticket_detail', ticket_id=ticket_id)

    context = {
        'ticket': ticket,
        'messages_list': messages_list,
    }
    return render(request, 'students/ticket_detail.html', context)


# ---------------------------------------------------------------------------

def get_current_semester():
    """Returns current semester based on month."""
    month = timezone.now().month
    if 10 <= month <= 2:
        return 1  # First semester
    elif 2 <= month <= 6:
        return 2  # Second semester
    else:
        return 3  # Summer

@student_required
def drop_by_code(request):
    if request.method != 'POST':
        return redirect('apps.students:services')

    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()
    code = request.POST.get('subject_code', '').strip()

    enrollment = Enrollment.objects.filter(
        student=student,
        section__subject__code__iexact=code,
        section__semester=current_semester,
        section__year=current_year,
        status='active'  # can't drop already dropped
    ).first()

    if not enrollment:
        messages.error(request, f'لا يوجد تسجيل فعال لمادة برمز {code} في هذا الفصل.')
    else:
        enrollment.status = 'dropped'
        enrollment.save()
        messages.success(request, f'تم اسقاط مادة {enrollment.section.subject.name} بنجاح.')

    return redirect('apps.students:services')

@student_required
def pdf_study_plan(request):
    student = request.user.student_profile
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="study_plan_{student.student_id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []

    # header
    story.append(Paragraph(ar('جامعة البلقاء التطبيقية'), ar_style(size=16)))
    story.append(Paragraph(ar(f'الخطة المفرغة للطالب: {student.full_name_ar}'), ar_style(size=13)))
    story.append(Paragraph(ar(f'الرقم الجامعي: {student.student_id}'), ar_style()))
    story.append(Paragraph(ar(f'التخصص: {student.major}'), ar_style()))
    story.append(Paragraph(ar(f'الكلية: {student.college}'), ar_style()))
    story.append(Spacer(1, 20))

    # group subjects by type
    from apps.courses.constants import SUBJECT_TYPES
    from apps.courses.models import Subject

    subjects = Subject.objects.filter(
        majors=student.major
    ).prefetch_related('prerequisites').order_by('subject_type', 'code')

    passed_ids = set(
        student.enrollments.filter(
            grade_points__isnull=False,
            grade_points__gt=0.5
        ).values_list('section__subject_id', flat=True)
    )

    passed_enrollments = {
        e.section.subject_id: e.symbol
        for e in student.enrollments.filter(grade_points__isnull=False)
        .select_related('section__subject')
    }

    for type_key, type_label in SUBJECT_TYPES:
        type_subjects = [s for s in subjects if s.subject_type == type_key]
        if not type_subjects:
            continue

        story.append(Paragraph(ar(type_label), ar_style(size=13)))
        story.append(Spacer(1, 6))

        # table header — reversed for RTL
        data = [[ar('الحالة'), ar('العلامة'), ar('الساعات'), ar('اسم المادة'), ar('الرمز')]]

        for subject in type_subjects:
            symbol = passed_enrollments.get(subject.id, '')
            if subject.id in passed_ids:
                status = ar('مكتملة')
            else:
                status = ar('لم تدرس')

            data.append([
                ar(status),
                ar(symbol),
                ar(str(subject.hours)),
                ar(subject.name),
                ar(subject.code),
            ])

        table = Table(data, colWidths=[70, 60, 60, 200, 80])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Amiri'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#119F61')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))

        story.append(table)
        story.append(Spacer(1, 16))

    doc.build(story)
    return response


@student_required
def pdf_schedule(request):
    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="schedule_{student.student_id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []

    # header
    story.append(Paragraph(ar('جامعة البلقاء التطبيقية'), ar_style(size=16)))
    story.append(Paragraph(ar(f'جدول الطالب: {student.full_name_ar}'), ar_style(size=13)))
    story.append(Paragraph(ar(f'الرقم الجامعي: {student.student_id}'), ar_style()))
    story.append(Paragraph(ar(f'الفصل الدراسي: {current_semester} / {current_year}'), ar_style()))
    story.append(Spacer(1, 20))

    hour_reg = student.hour_registrations.filter(
        semester=current_semester,
        year=current_year
    ).first()

    if not hour_reg:
        story.append(Paragraph(ar('لا يوجد تسجيل لهذا الفصل'), ar_style()))
        doc.build(story)
        return response

    enrollments = hour_reg.enrollments.select_related(
        'section__subject',
        'section__instructor',
        'section__room'
    ).prefetch_related('section__schedules')

    # table header
    data = [[
        ar('الأيام'),
        ar('الوقت'),
        ar('القاعة'),
        ar('المحاضر'),
        ar('الساعات'),
        ar('اسم المادة'),
        ar('الرمز'),
    ]]

    for enrollment in enrollments:
        section = enrollment.section
        schedules = section.schedules.all()
        days = ' / '.join(s.get_day_display() for s in schedules)
        times = ' / '.join(f'{s.start_time.strftime("%H:%M")}-{s.end_time.strftime("%H:%M")}' for s in schedules)
        instructor = f'{section.instructor.first_name_ar} {section.instructor.last_name_ar}'

        data.append([
            ar(days),
            ar(times),
            ar(str(section.room)),
            ar(instructor),
            ar(str(section.subject.hours)),
            ar(section.subject.name),
            ar(section.subject.code),
        ])

    table = Table(data, colWidths=[60, 80, 50, 90, 45, 120, 60])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Amiri'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#119F61')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    doc.build(story)
    return response