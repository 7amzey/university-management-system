# University Management System — نظام التسجيل الإلكتروني

A full-featured electronic registration portal for **Al-Balqa Applied University – Faculty of Technological Engineering**, built with Django and Bootstrap 5 RTL. The system serves three user types — students, instructors, and staff — each with their own interface and authentication flow.

---

## Features

### Student Portal
- Login via student ID and password with password reset via email
- Course catalog with real-time schedule conflict detection
- Pending enrollment basket (zero DB writes until confirmed)
- Drop subjects from schedule with automatic balance refund
- Finance page with semester balance wallet, enrollment charges, and service fees
- GPA and academic standing tracking
- Downloadable PDF schedule and study plan (Arabic, RTL)
- Support ticket system with full conversation thread
- Unread announcements badge and notification center
- Light / Dark theme toggle

### Staff / Admin
- Full Django admin interface
- Student and instructor management
- Course section management with multi-instructor and multi-room support per section
- Grade entry (midterm, participation, final) with automatic weighted total calculation
- Grade distribution ranges and symbol assignment per subject per semester
- Registration period and window management (by student credit hours)
- Payment confirmation portal — look up student by ID and confirm pending charges
- Section request approval (when a section is full, student can request opening)
- Announcement broadcasting (global or per-student)
- Ticket management and staff replies

### Academic System
- Weighted grading: Midterm 30% · Participation 20% · Final 50%
- GPA symbols: A (4.0) → F* (0.5)
- Prerequisite enforcement before enrollment
- Major study plan with subject type grouping
- Passed/failed hour tracking for registration window eligibility

### Finance System
- Two-transaction model on registration: semester hours charge + separate registration fee
- Semester payment becomes a **balance credit** (wallet)
- Each enrollment deducts `subject hours × hour price` from balance automatically
- Dropping a subject restores the balance instantly
- Service fees (clinic, transcript, clearance, etc.) are isolated — never affect balance
- Balance carries forward to the next semester

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6 |
| Database | SQLite (dev) |
| Frontend | Bootstrap 5.3 RTL |
| PDF Generation | ReportLab + arabic-reshaper + python-bidi |
| Arabic Font | Amiri |
| Email | Gmail SMTP |
| Authentication | Custom multi-backend (Student ID / Employee ID / Email) |

---

## Project Structure

```
apps/
├── accounts/        — Custom User model, auth backends, split session middleware
├── academics/       — College, Department, Major, MajorSubjectRequirement
├── facilities/      — Building, Room
├── courses/         — Subject, CourseSection, SectionSchedule, ExamSchedule,
│                      GradeDistribution, RegistrationPeriod, RegistrationWindow, SectionRequest
├── instructors/     — Instructor
├── students/        — Student, HourRegistration, Enrollment, finance views, PDF views
├── finance/         — Transaction
├── announcements/   — Announcement
└── tickets/         — Ticket, TicketMessage
```

## Authentication

The system uses three separate authentication backends simultaneously:

| User Type | Login Field | Portal |
|---|---|---|
| Student | Student ID | `/student/` |
| Instructor | Employee ID | `/instructor/` |
| Staff | Email | `/admin/` |

A custom split session middleware keeps student and admin sessions completely independent, allowing both to be active at the same time in the same browser.

---

## PDF Generation Notes

- Both PDFs (schedule and study plan) are generated in Arabic RTL using ReportLab
- The Amiri font must be present at `static/fonts/Amiri-Regular.ttf`
- arabic-reshaper and python-bidi handle correct Arabic letter shaping and text direction

---

## Key Concepts

**Registration Flow:**
Student requests hours → staff confirms payment → balance credited → student selects subjects → per-subject charges deducted from balance → leftover balance carries forward

**Enrollment conflict detection:**
Checks confirmed enrollments, pending additions, and excludes pending drops — all before any DB write

**Grade assignment:**
Staff enters min/max ranges per symbol per subject per semester → `assign_symbols()` action in admin distributes symbols to all enrollments automatically

---

## Requirements

```
django
reportlab
arabic-reshaper
python-bidi
pillow
```

---

## License

This project is for educational purposes.