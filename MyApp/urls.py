# pyrefly: ignore [missing-import]
from django.urls import path
# pyrefly: ignore [missing-import]
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('detect/', views.teacher_detect, name='teacher_detect'),
    path('student/actions/', views.student_actions, name='student_actions'),
    path('student/assignments/', views.student_assignments, name='student_assignments'),
    path('student/materials/', views.student_materials, name='student_materials'),
    path('student/pastpapers/', views.student_pastpapers, name='student_pastpapers'),
    path('student/progress/', views.student_progress, name='student_progress'),
    path('student/quiz/', views.student_quiz, name='student_quiz'),
    path('student/results/', views.student_results, name='student_results'),
    path('teacher/actions/', views.teacher_actions, name='teacher_actions'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/invite/', views.teacher_invite, name='teacher_invite'),
    path('profile/', views.profile_view, name='profile'),
    path('teacher/assignment/', views.teacher_assignment, name='teacher_assignment'),
    path('assignment/<int:assignment_id>/submit/', views.submit_assignment, name='submit_assignment'),
    path('teacher/assignment/<int:assignment_id>/submissions/', views.teacher_submissions, name='teacher_submissions'),
    path('submission/<int:submission_id>/detect/', views.detect_submission, name='detect_submission'),
    path('teacher/materials/', views.teacher_materials, name='teacher_materials'),
    path('teacher/material/<int:material_id>/detect/', views.teacher_material_detect, name='teacher_material_detect'),
    path('teacher/pastpaper/', views.teacher_pastpaper, name='teacher_pastpaper'),
    path('teacher/pastpaper/<int:material_id>/delete/', views.delete_pastpaper, name='delete_pastpaper'),
    path('teacher/assignment/<int:assignment_id>/delete/', views.delete_assignment, name='delete_assignment'),
    path('teacher/material/<int:material_id>/delete/', views.delete_material, name='delete_material'),
    path('teacher/invitation/<int:invitation_id>/delete/', views.delete_invitation, name='delete_invitation'),
    path('teacher/results/', views.teacher_results, name='teacher_results'),
]
