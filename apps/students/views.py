from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Count, Sum, F
from django.db import models as db_models
from django.utils import timezone
from django.http import HttpResponse

from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

from .pdf_utils import ar, ar_style
from apps.courses.constants import SUBJECT_TYPES
from apps.tickets.models import Ticket, TicketMessage
from apps.announcements.models import Announcement
from apps.students.models import Student, HourRegistration, Enrollment, absence
from apps.courses.models import SectionSchedule, Subject, CourseSection, ExamSchedule, RegistrationPeriod, SectionRequest

# login view for students
def student_login(request):
    # if already logged in and session indicates student portal, redirect to dashboard
    if request.user.is_authenticated and request.session.get('is_student_portal'):
        return redirect('students:dashboard')

    # on POST, attempt authentication with student_id and password
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        password = request.POST.get('password')

        user = authenticate(request, student_id=student_id, password=password)

        # ensure user is a student before logging in and setting session flag
        if user and user.role == 'student':
            # login with our custom backend to avoid conflicts with other user types
            login(request, user, backend='apps.accounts.backends.StudentBackend')
            request.session['is_student_portal'] = True
            return redirect('apps.students:dashboard')
        else:
            messages.error(request, 'رقم الطالب أو كلمة السر غير صحيحة.')

    return render(request, 'students/login.html')

# logout view for students
def student_logout(request):
    logout(request)
    return redirect('apps.students:login')

# decorator to require student login and check session flag to prevent access with other user types
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

# student dashboard view showing student's info, current schedule, exams, and absences
@student_required
def dashboard(request):
    student = request.user.student_profile

    today_day = timezone.now().weekday()
    today_schedule = []

    # get latest registration to determine current enrollments and exams
    latest_reg = student.hour_registrations.order_by('-year', '-semester').first() 
    current_enrollments = []
    midterm_exams = []
    final_exams = []

    absences = absence.objects.filter(enrollment__student=student) # get all absences for this student across all enrollments

    # check if there is a registration before trying to access enrollments and exams to avoid errors for students with no registrations yet
    if latest_reg:
        
        # retrive all enrollments for this registration with related subject and schedule info to minimize DB queries
        current_enrollments = latest_reg.enrollments.select_related(
            'section__subject'
        ).prefetch_related('section__schedules__room')

        # get today's schedule by filtering enrollments for sections that have a schedule on the current day, then select related subject and prefetch room info for display
        today_schedule = SectionSchedule.objects.filter(
            section__in=[e.section for e in current_enrollments],
            day=today_day
        ).select_related(
            'section__subject'
        ).prefetch_related('section__schedules__room').order_by('start_time')

        # get midterm and final exams for current enrollments by filtering ExamSchedule for sections in current enrollments and separating by mid=True/False, then select related subject info for display
        midterm_exams = ExamSchedule.objects.filter(
            section__in=[e.section for e in current_enrollments],
            mid=True
        ).select_related('section__subject').order_by('date', 'start_time')

        # get final exams same as midterm but with mid=False
        final_exams = ExamSchedule.objects.filter(
            section__in=[e.section for e in current_enrollments],
            mid=False
        ).select_related('section__subject').order_by('date', 'start_time')

    context = {
        'student': student,
        'gpa': student.gpa,
        'balance': student.balance,
        'latest_reg': latest_reg,
        'current_enrollments': current_enrollments,
        'midterm_exams': midterm_exams,
        'final_exams': final_exams,
        'absences': absences,
        'today_schedule': today_schedule,
    }
    return render(request, 'students/dashboard.html', context)


"""
    finance view where students can see their transactions, register hours, and see pending charges.
    Handles both GET for display and POST for updating hour registration. 
    Validates requested hours against student's min/max and updates or creates HourRegistration accordingly.
    Also calculates pending charges based on unpaid transactions.
"""
@student_required
def finance(request):
    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()

    # check if there's an existing hour registration for this semester to pre-fill the form and determine if we're updating or creating
    existing_reg = HourRegistration.objects.filter(
        student=student,
        semester=current_semester,
        year=current_year
    ).first()

    # on POST, validate requested hours and update or create HourRegistration, then redirect to avoid resubmission
    if request.method == 'POST':
        # first validate that the input is a number and within the student's allowed range of hours before saving to DB
        try:
            requested_hours = int(request.POST.get('requested_hours')) # requested hours is form input
            if requested_hours < student.min_hours or requested_hours > student.max_hours: # validate against student's min and max hours
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
                # calculate difference from paid hours to determine if we need to charge or refund the student based on whether they increased or decreased their hours
                difference = requested_hours - existing_reg.paid_hours
                if difference > 0:
                    messages.success(request, f'تم زيادة الساعات إلى {requested_hours}، سيتم احتساب رسوم إضافية لـ {difference} ساعة.')
                elif difference < 0:
                    messages.success(request, f'تم تخفيض الساعات إلى {requested_hours}، سيتم استرداد رسوم {abs(difference)} ساعة.')
                else:
                    messages.success(request, f'تم إرجاع الساعات إلى {requested_hours}.')
            else:
                messages.success(request, f'تم تحديث تسجيل الساعات إلى {requested_hours} ساعة.')

            # update the existing registration with the new requested hours 
            # this will call the save method which will handle creating transactions based on the registration status
            existing_reg.requested_hours = requested_hours
            existing_reg.save()

        # if no existing registration, create a new one with the requested hours which will also trigger transaction creation in the save method
        else:
            HourRegistration.objects.create(
                student=student,
                semester=current_semester,
                year=current_year,
                requested_hours=requested_hours
            )
            messages.success(request, f'تم تسجيل {requested_hours} ساعة بنجاح.')

        return redirect('apps.students:finance')

    # for GET request, fetch all transactions for the student ordered by date to display in the template
    transactions = student.transactions.order_by('-date')

    # calculate total pending charges by filtering transactions for unpaid charges and summing their amounts, defaulting to 0 if there are none
    pending = transactions.filter(
        transaction_type='charge',
        is_paid=False
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'student': student,
        'transactions': transactions,
        'total_payments': student.balance,
        'pending': pending,
        'existing_reg': existing_reg,
        'current_semester': current_semester,
        'current_year': current_year,
    }
    return render(request, 'students/finance.html', context)


# view to look up payment status by student ID and redirect to confirmation page if found, otherwise show error message
def payment_lookup(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        try:
            # just to validate that the student ID exists before redirecting to confirmation page, actual payment status will be checked on confirmation page
            student = Student.objects.get(student_id=student_id)
            return redirect('apps.students:payment_confirm', student_id=student_id)
        except Student.DoesNotExist:
            messages.error(request, 'رقم الطالب غير موجود.')
    return render(request, 'students/payment_lookup.html')


# view to confirm payment for a student by marking all pending transactions as paid and updating hour registration status, then redirecting back to lookup page with success message
def payment_confirm(request, student_id):
    student = get_object_or_404(Student, student_id=student_id)
    current_year = timezone.now().year
    current_semester = get_current_semester()

    # fetch all pending charge transactions for this student 
    pending_transactions = student.transactions.filter(
        transaction_type='charge',
        is_paid=False
    )

    # calculate total pending amount to display in confirmation message after marking as paid
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


"""
    current_grades view to display the student's current semester grades by fetching the latest hour 
    registration and related enrollments ,then passing them to the template for display. 
    Also handles case where there is no registration yet.
"""
@student_required
def current_grades(request):
    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()

    # fetch the current hour registration for this student to determine which enrollments to show, if any
    current_reg = HourRegistration.objects.filter(
        student=student,
        semester=current_semester,
        year=current_year
    ).first()

    enrollments = []
    if current_reg:
        # fetch all enrollments for this registration with related subject info to minimize DB queries, and order by subject name for display
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


"""
    grade_history view to display the student's grade history by fetching all past hour registrations that are paid
    , then for each registration fetching the related enrollments with grades and calculating semester GPA
    , finally passing all this info to the template for display.
"""
@student_required
def grade_history(request):
    student = request.user.student_profile

    # get all registrations ordered by year and semester
    registrations = student.hour_registrations.filter(
        is_paid=True
    ).order_by('-year', '-semester')

    semesters = []
    for reg in registrations:
        # fetch enrollments for this registration that have a grade (symbol is not null) with related subject info to minimize DB queries
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


"""
    subject_catalog view to display the subjects available for the student's major, grouped by type
    , and indicating which ones have been passed or are currently enrolled in.
"""
@student_required
def subject_catalog(request):
    student = request.user.student_profile

    # fetch all subjects for this student's major with related prerequisites to minimize DB queries, and order by type and code for display
    subjects = Subject.objects.filter(
        majors=student.major
    ).prefetch_related('prerequisites').order_by('subject_type', 'code')

    # get IDs of subjects the student has passed (grade_points > 0.5 means above D-) 
    passed_subject_ids = set(
        student.enrollments.filter(
            grade_points__isnull=False,
            grade_points__gt=0.5
        ).values_list('section__subject_id', flat=True)
    )

    # get IDs of subjects the student is currently enrolled in (symbol is null means not graded yet)
    enrolled_subject_ids = set(
        student.enrollments.filter(
            symbol__isnull=True
        ).values_list('section__subject_id', flat=True)
    )

    # also create a dict of passed enrollments keyed by subject ID to show the grade symbol in the catalog if needed
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

    # group subjects by type for display, and calculate total hours, passed hours, and required hours for each type to show progress towards graduation requirements
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

    context = {
        'student': student,
        'catalog': catalog,
        'passed_subject_ids': passed_subject_ids,
        'enrolled_subject_ids': enrolled_subject_ids,
        'passed_enrollments': passed_enrollments,
    }
    return render(request, 'students/subject_catalog.html', context)


"""
    announcements view to display global and student-specific announcements
    , and update the student's last seen timestamp to manage unread badges.
"""
@student_required
def announcements(request):
    student = request.user.student_profile
    last_seen = student.announcements_last_seen

    # fetch global + student-specific announcements and order by most recent
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


"""
    view to display student's profile information
"""
@student_required
def profile(request):
    student = request.user.student_profile
    return render(request, 'students/profile.html', {'student': student})



"""
    course_catalog view to display the student's current schedule with confirmed and pending sections, eligible subjects
    for enrollment, and handle adding/removing pending sections and confirming enrollment changes.
"""
@student_required
def course_catalog(request):
    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()

    # fetch the current registration period to determine if enrollment is open
    period = RegistrationPeriod.objects.filter(
        semester=current_semester,
        year=current_year,
        is_open=True
    ).first()

    # if there's an active registration period, get the enrollment window for this student 
    window = period.get_window_for_student(student) if period else None

    # get all windows for this period that the student is eligible for based on their completed hours
    student_windows = period.windows.filter(
        min_hours__lte=student.passed_hours + student.failed_hours,
        max_hours__gte=student.passed_hours + student.failed_hours
    ).order_by('start_datetime') if period else None

    # fetch the current hour registration for this student to determine current enrollments and pending changes
    hour_reg = HourRegistration.objects.filter(
        student=student,
        semester=current_semester,
        year=current_year,
        is_paid=True
    ).first()

    # handle POST actions for confirming drops, adding pending sections, and removing pending sections, then redirect to avoid resubmission
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'drop_confirmed':
            # when droping a confirmd enrollment we add it to the pending drops list in the session
            # , which will be processed when the student confirms their schedule changes
            enrollment_id = request.POST.get('enrollment_id')
            pending_drops = get_pending_drops(request)
            if enrollment_id not in pending_drops:
                pending_drops.append(enrollment_id)
                set_pending_drops(request, pending_drops)
        elif action == 'remove_pending':
            # removing a pending section just means removing it from the pending sections dict in the session,
            # which will update the display and not include it in the schedule when the student confirms their changes
            section_id = request.POST.get('section_id')
            subject_id = CourseSection.objects.get(id=section_id).subject.id
            pending_dict = get_pending_sections(request)
            pending_dict.pop(str(subject_id), None)
            set_pending_sections(request, pending_dict)
            messages.success(request, f'تمت إزالة {CourseSection.objects.get(id=section_id).subject.name} من جدولك المؤقت.')
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

    # get all confirmed enrollments for this hour registration with related subject and schedule info to minimize DB queries
    confirmed_enrollments = Enrollment.objects.filter(
        hour_registration=hour_reg
    ).select_related('section__subject').prefetch_related('section__schedules__instructor', 'section__schedules__room')

    # calculate confirmed subject IDs and hours for display and validation purposes
    confirmed_subject_ids = set(e.section.subject_id for e in confirmed_enrollments)
    confirmed_hours = sum(
        e.section.subject.hours for e in confirmed_enrollments
    )

    # if there's an active registration period and enrollment window, and the student has a paid hour registration, we can calculate pending sections, hours, and eligible subjects 
    # for enrollment based on the pending sections in the session and the student's completed hours to show the student what they can add to their schedule and how it affects their total hours.
    if period and window and hour_reg:
        if pending_dict:
            # fetch pending sections based on the IDs in the pending_dict from the session, and select related subject and schedule info to minimize DB queries
            pending_sections = list(
                CourseSection.objects.filter(
                    id__in=pending_dict.values()
                ).select_related('subject').prefetch_related('schedules__instructor', 'schedules__room')
            )


        # calculate pending hours based on the subjects of the pending sections for display and validation purposes
        pending_hours = sum(s.subject.hours for s in pending_sections)
        pending_subject_ids = {int(k) for k in pending_dict.keys()}

        # get eligible subjects for enrollment based on the student's completed hours and the current registration window, 
        # and filter to only include those that have available sections in the current semester and year to show the student what they can add to their schedule.
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
            'instructor': enrollment.section.instructors,
            'room': enrollment.section.rooms,
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
            'instructor': section.instructors,
            'room': section.rooms,
            'status': 'pending',
            'enrollment_id': None,
        })

    # sort schedule by day and start time, with pending sections at the end if they have no schedules to avoid errors in the template
    schedule.sort(key=lambda x: (x['schedules'][0].day, x['schedules'][0].start_time) if x['schedules'] else (99, 99))

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


"""
    view to display available sections for a subject and handle adding/removing pending sections,
    requesting full sections, and dropping confirmed enrollments for that subject, 
    with validation for schedule conflicts and enrollment limits.
"""
@student_required
def subject_sections(request, subject_id):
    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()

    # fetch the subject based on the ID in the URL, or return 404 if not found
    subject = get_object_or_404(Subject, id=subject_id)

    # fetch the current hour registration for this student 
    hour_reg = HourRegistration.objects.filter(
        student=student,
        semester=current_semester,
        year=current_year,
        is_paid=True
    ).first()

    # if there's no paid hour registration, the student shouldn't be able to enroll in any sections
    if not hour_reg:
        messages.error(request, 'يجب دفع رسوم تسجيل الساعات أولاً.')
        return redirect('apps.students:finance')

    # fetch all sections for this subject in the current semester and year with related schedule, instructor, and room info to minimize DB queries,
    # and annotate with confirmed enrollment count for display and validation purposes
    sections = CourseSection.objects.filter(
        subject=subject,
        semester=current_semester,
        year=current_year
    ).prefetch_related('schedules', 'schedules__instructor', 'schedules__room').annotate(confirmed_count=Count('enrollments'))

    # check if the student has a confirmed enrollment for this subject 
    confirmed_enrollment = Enrollment.objects.filter(
        student=student,
        section__subject=subject,
        section__semester=current_semester,
        section__year=current_year
    ).first()

    # get pending section ID for this subject from the session
    pending_dict = get_pending_sections(request)
    pending_section_id = pending_dict.get(str(subject_id))

    # get IDs of sections for this subject that the student has requested to enroll in but are still pending approval, to show the status in the template
    requested_section_ids = set(
        SectionRequest.objects.filter(
            student=student,
            section__subject=subject,
            status='pending'
        ).values_list('section_id', flat=True)
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        # if the action is not drop confirmed subject then we need to get the section ID from the form
        if action != 'drop_confirmed':
            section_id = int(request.POST.get('section_id'))
            section = get_object_or_404(CourseSection, id=section_id)

        # validate that the action is one of the allowed actions to prevent invalid form submissions
        if action not in ['enroll', 'remove_pending', 'request', 'drop_confirmed']:
            messages.error(request, 'إجراء غير صالح.')
            return redirect('apps.students:subject_sections', subject_id=subject_id)

        # handle enrolling in a section by first checking if it's full, then checking for schedule conflicts with existing confirmed enrollments and pending sections, and if all checks pass, add it to the pending sections in the session
        if action == 'enroll':
            if section.enrollments.count() >= section.capacity:
                messages.error(request, 'هذه الشعبة ممتلئة.')
                return redirect('apps.students:subject_sections', subject_id=subject_id)

            new_schedules = list(section.schedules.all())
            conflict = False
            conflict_subject = ''
            pending_drops = get_pending_drops(request)
            for enrollment in Enrollment.objects.filter(
                hour_registration=hour_reg
            ).exclude(section__subject=subject).exclude(id__in=pending_drops).prefetch_related('section__schedules'):
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
            return redirect('apps.students:course_catalog')

        # handle removing a pending section by removing it from the pending sections in the session
        elif action == 'remove_pending':
            pending_dict.pop(str(subject_id), None)
            set_pending_sections(request, pending_dict)
            messages.success(request, f'تمت إزالة {subject.name} من جدولك المؤقت.')

        # handle requesting a full section by creating a SectionRequest object with status pending, and also create an announcement for the admin to review the request
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

        # handle droping a confirmed enrollment by adding it to the pending drops list in the session, which will be processed when the student confirms their schedule changes
        elif action == 'drop_confirmed':
            enrollment_id = request.POST.get('enrollment_id')
            pending_drops = get_pending_drops(request)
            if enrollment_id not in pending_drops:
                pending_drops.append(enrollment_id)
                set_pending_drops(request, pending_drops)
                messages.success(request, f'تمت إضافة {subject.name} إلى المواد الغير مثبتة للحذف.')
            else:
                messages.success(request, f'{subject.name} بالفعل في المواد الغير مثبتة للحذف.')

        return redirect('apps.students:subject_sections', subject_id=subject_id)

    context = {
        'subject': subject,
        'sections': sections,
        'confirmed_enrollment': confirmed_enrollment,
        'pending_section_id': pending_section_id,
        'requested_section_ids': requested_section_ids,
        'pending_drops': get_pending_drops(request),
    }
    return render(request, 'students/subject_sections.html', context)


"""
    view to handle confirming enrollment changes by validating that the total hours with pending sections and drops still meets the student's requirements
    and doesn't exceed their hour registration, then applying the changes to the database in a single transaction for efficiency, 
    and finally clearing the pending sections and drops from the session.
"""
@student_required
def submit_enrollment(request):
    # this view is only for processing the final confirmation of schedule changes, so it should only accept POST requests, otherwise redirect back to the course catalog
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

    # if there's no paid hour registration, the student shouldn't be able to confirm any enrollment changes, so show an error message and redirect back to the finance page where they can pay for their hours
    if not hour_reg:
        messages.error(request, 'يجب دفع رسوم تسجيل الساعات أولاً.')
        return redirect('apps.students:finance')

    pending_drops = get_pending_drops(request)
    pending_dict = get_pending_sections(request)    

    # if there are no pending sections to add and no pending drops, then there's nothing to confirm, so show an info message and redirect back to the course catalog
    if not pending_dict and not pending_drops:
        messages.info(request, 'لا توجد مواد غير مثبتة للتأكيد.')
        return redirect('apps.students:course_catalog')

    # calculate confirmed hours based on the student's current enrollments for this hour registration, excluding any that are pending drop, to use for validating against the student's minimum hours requirement and hour registration limit when we add pending sections and remove pending drops
    confirmed_hours = Enrollment.objects.filter(
        hour_registration=hour_reg
    ).aggregate(
        total=Sum('section__subject__hours')
    )['total'] or 0

    # if there are pending drops, we need to validate that dropping those sections won't put the student below their minimum hours requirement before we can apply the drops
    if pending_drops:
        if confirmed_hours - sum(e.section.subject.hours for e in Enrollment.objects.filter(id__in=pending_drops, student=student)) < student.min_hours:
            messages.error(
                request,
                f'لا يمكنك حذف هذه المواد لأنها ستقلل ساعاتك إلى أقل من الحد الأدنى ({student.min_hours} ساعة).'
            )
            set_pending_drops(request, [])
            return redirect('apps.students:course_catalog')
        else:
            # if the validation passes, we can safely delete the pending drops from the database, which will also cascade and delete any related SectionRequests for those enrollments, and then clear the pending drops from the session
            Enrollment.objects.filter(id__in=pending_drops, student=student).delete()
            set_pending_drops(request, [])
            messages.success(request, f'تم حذف {len(pending_drops)} مادة من جدولك.')
            return redirect('apps.students:course_catalog')

    # if there are pending sections to add, we need to validate that adding those sections won't put the student below their minimum hours requirement or exceed their hour registration limit before we can apply the additions
    pending_sections = list(
        CourseSection.objects.filter(
            id__in=pending_dict.values()
        ).select_related('subject')
    )

    # calculate pending hours based on the subjects of the pending sections for validating against the student's minimum hours requirement and hour registration limit when we add pending sections and remove pending drops
    pending_hours = sum(s.subject.hours for s in pending_sections)
    total_hours = confirmed_hours + pending_hours

    # validate that the total hours with pending sections and drops still meets the student's minimum hours requirement, and if not, show an error message and redirect back to the course catalog without applying any changes
    if total_hours < student.min_hours:
        messages.error(
            request,
            f'مجموع الساعات ({total_hours}) أقل من الحد الأدنى ({student.min_hours} ساعة).'
        )
        return redirect('apps.students:course_catalog')

    # validate that the total hours with pending sections and drops doesn't exceed the student's hour registration, and if it does, show an error message and redirect back to the course catalog without applying any changes
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

    clear_pending_sections(request)
    messages.success(request, f'تم تأكيد تسجيل {len(pending_sections)} مادة بنجاح.')
    return redirect('apps.students:course_catalog')


"""
    view to display available student services such as submitting support tickets and dropping by code, and handle the corresponding actions for those services.
"""
@student_required
def services(request):
    return render(request, 'students/services.html')


"""
    view to handle dropping a course by code
"""
@student_required
def drop_by_code(request):
    if request.method != 'POST':
        return redirect('apps.students:services')

    student = request.user.student_profile
    current_year = timezone.now().year
    current_semester = get_current_semester()
    reg_period = RegistrationPeriod.objects.filter(
        semester=current_semester,
        year=current_year,
        is_open=True
    ).first()
    code = request.POST.get('subject_code', '').strip()

    # validate that the student has an active enrollment for the subject code in the current semester and year
    enrollment = Enrollment.objects.filter(
        student=student,
        section__subject__code__iexact=code,
        section__semester=current_semester,
        section__year=current_year,
        status='active'  # can't drop already dropped
    ).first()

    # if there's no active registration period, allow the drop to be processed by marking the enrollment as dropped, 
    # otherwise show an error message that drops can't be done during the registration period and redirect back to the services page
    if not reg_period:
        if not enrollment:
            messages.error(request, f'لا يوجد تسجيل فعال لمادة برمز {code} في هذا الفصل.')
        else:
            enrollment.status = 'dropped'
            enrollment.save()
            messages.success(request, f'تم اسقاط مادة {enrollment.section.subject.name} بنجاح.')
    else:
        messages.error(request, 'لا يمكن استخدام هذا الخيار أثناء فترة التسجيل. الرجاء استخدام صفحة تسجيل المواد لإجراء التعديلات على جدولك.')

    return redirect('apps.students:services')


"""
    view to handle submitting a support ticket by creating a new Ticket and TicketMessage based on the form data, and validating that all required fields are provided before saving to the database.
"""
@student_required
def submit_ticket(request):
    if request.method != 'POST':
        return redirect('apps.students:dashboard')

    student = request.user.student_profile
    category = request.POST.get('category')
    subject = request.POST.get('subject', '').strip()
    body = request.POST.get('body', '').strip()

    # validate that all required fields are provided, and if not, return a 400 Bad Request response to indicate that the form submission is invalid
    if not subject or not body or not category:
        return HttpResponse(status=400)

    # create a new Ticket with the provided category and subject, associated with the current student
    ticket = Ticket.objects.create(
        student=student,
        category=category,
        subject=subject,
    )

    # create a new TicketMessage for the initial message in the ticket with the provided body and the current user as the sender
    TicketMessage.objects.create(
        ticket=ticket,
        sender=request.user,
        body=body
    )

    return HttpResponse(status=200)


"""
    view to display the list of support tickets for the current student
"""
@student_required
def tickets_list(request):
    student = request.user.student_profile
    tickets = student.tickets.all()
    context = {
        'tickets': tickets,
    }
    return render(request, 'students/tickets_list.html', context)


"""
    view to display the details of a support ticket and handle adding new messages to the ticket, with validation to prevent adding messages to closed tickets.
"""
@student_required
def ticket_detail(request, ticket_id):
    student = request.user.student_profile
    ticket = get_object_or_404(Ticket, id=ticket_id, student=student)
    messages_list = ticket.messages.select_related('sender')

    if request.method == 'POST':
        # validate that the ticket is not closed before allowing a new message to be added
        if ticket.status == 'closed':
            messages.error(request, 'هذه التذكرة مغلقة ولا يمكن الرد عليها.')
            return redirect('apps.students:ticket_detail', ticket_id=ticket_id)

        # validate that the message body is not empty
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

@student_required
def pdf_study_plan(request):
    student = request.user.student_profile
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="study_plan_{student.student_id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []

    from apps.students.pdf_utils import pdf_header
    pdf_header(story, [
        f'الخطة المفرغة للطالب: {student.full_name_ar}',
        f'الرقم الجامعي: {student.student_id}',
        f'التخصص: {student.major}',
        f'الكلية: {student.college}',
    ])

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
        data = [[ar('المتطلبات السابقة'), ar('الحالة'), ar('العلامة'), ar('الساعات'), ar('اسم المادة'), ar('الرمز')]]

        for subject in type_subjects:
            symbol = passed_enrollments.get(subject.id, '')
            if subject.id in passed_ids:
                status = 'مكتملة'
            else:
                status = 'لم تدرس'

            prereqs = '\n'.join(s.code for s in subject.prerequisites.all()) or '—'
            data.append([
                ar(prereqs),
                ar(status),
                ar(symbol),
                ar(str(subject.hours)),
                ar(subject.name),
                ar(subject.code),
            ])

        table = Table(data, colWidths=[120, 60, 50, 50, 160, 70])
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
    from apps.students.pdf_utils import pdf_header
    pdf_header(story, [
        f'جدول الطالب: {student.full_name_ar}',
        f'الرقم الجامعي: {student.student_id}',
        f'الفصل الدراسي: {current_semester} / {current_year}',
    ])

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
    ).prefetch_related('section__schedules', 'section__schedules__instructor', 'section__schedules__room')

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
        days = '\n'.join(s.get_day_display() for s in schedules)
        times = '\n'.join(f'{s.start_time.strftime("%H:%M")}-{s.end_time.strftime("%H:%M")}' for s in schedules)
        instructors = '\n'.join(dict.fromkeys(
            f'{s.instructor.first_name_ar} {s.instructor.last_name_ar}'
            for s in schedules if s.instructor
        ))
        rooms = '\n'.join(dict.fromkeys(
            str(s.room) for s in schedules if s.room
        ))

        data.append([
            ar(days),
            ar(times),
            ar(rooms),
            ar(instructors),
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


"""
    *****************************************************************************************************
    Helper functions to manage pending enrollments and drops in the session during the enrollment process
    *****************************************************************************************************
"""

def get_current_semester():
    """Returns current semester based on month."""
    month = timezone.now().month
    if 10 <= month <= 2:
        return 1  # First semester
    elif 2 <= month <= 6:
        return 2  # Second semester
    else:
        return 3  # Summer

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