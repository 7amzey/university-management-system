from django.urls import path
from apps.students import views

app_name = 'apps.students'

urlpatterns = [
    path('login/', views.student_login, name='login'),
    path('logout/', views.student_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('finance/', views.finance, name='finance'),
    path('payment/', views.payment_lookup, name='payment_lookup'),
    path('payment/<str:student_id>/', views.payment_confirm, name='payment_confirm'),
    path('grades/', views.current_grades, name='current_grades'),
    path('grades/history/', views.grade_history, name='grade_history'),
    path('catalog/', views.subject_catalog, name='subject_catalog'),
    path('announcements/', views.announcements, name='announcements'),
    path('profile/', views.profile, name='profile'),
    path('courses/', views.course_catalog, name='course_catalog'),
    path('courses/submit/', views.submit_enrollment, name='submit_enrollment'),
    path('courses/<int:subject_id>/sections/', views.subject_sections, name='subject_sections'),
    path('courses/drop/<int:enrollment_id>/', views.drop_section, name='drop_section'),
]