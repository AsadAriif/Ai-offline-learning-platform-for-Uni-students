# pyrefly: ignore [missing-import]
from django.shortcuts import render, redirect
# pyrefly: ignore [missing-import]
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
# pyrefly: ignore [missing-import]
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie, get_token, csrf_exempt
import re
from django.db import models
from django.utils import timezone
from .models import Submission, Message, Course, Assignment, Material, Enrollment, CustomUser, QuizQuestion, TeacherTask, TeacherAttendance, MarksheetSubmission, Notification
from django.http import JsonResponse


def parse_fill_in_blanks(text):
    blanks = re.findall(r'\[\[(.+?)\]\]', text)
    if blanks:
        return blanks
    underscores = re.findall(r'_{2,}', text)
    return [f'Blank {i + 1}' for i, _ in enumerate(underscores)] if underscores else []


def index(request):
    return render(request, 'MyApp/index.html')

def login_view(request):
    if request.user.is_authenticated:
        user_role = getattr(request.user, 'role', '')
        if user_role == 'hod':
            return redirect('hod_dashboard')
        elif user_role == 'teacher':
            return redirect('teacher_dashboard')
        return redirect('student_dashboard')

    if request.method == 'POST':
        username = request.POST.get('student_id')
        password = request.POST.get('password')
        role = request.POST.get('role')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if role:
                if getattr(user, 'role', None) == role:
                    auth_login(request, user)
                    if role == 'hod':
                        return redirect('hod_dashboard')
                    elif role == 'teacher':
                        return redirect('teacher_dashboard')
                    else:
                        return redirect('student_dashboard')
                else:
                    role_map = {'hod': 'Head of Department (HOD)', 'teacher': 'Teacher / Faculty', 'student': 'Student'}
                    messages.error(request, f"Access Denied: You are not registered as a {role_map.get(role, role.capitalize())}.")
            else:
                auth_login(request, user)
                u_role = getattr(user, 'role', '')
                if u_role == 'hod':
                    return redirect('hod_dashboard')
                elif u_role == 'teacher':
                    return redirect('teacher_dashboard')
                else:
                    return redirect('student_dashboard')
        else:
            messages.error(request, "Invalid User ID or Password")

    return render(request, 'MyApp/login.html')


def signup_view(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        role = request.POST.get('role', '').strip().lower()
        phone_number = request.POST.get('phone_number', '').strip()

        if not full_name or not username or not password or not role or not phone_number:
            messages.error(request, 'Please fill in all fields.')
            return redirect('signup')

        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return redirect('signup')

        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'This username already exists.')
            return redirect('signup')

        if role not in dict(CustomUser.ROLE_CHOICES):
            messages.error(request, 'Invalid role selected.')
            return redirect('signup')

        user = CustomUser.objects.create_user(
            username=username,
            password=password,
            role=role,
            phone_number=phone_number,
        )
        user.first_name = full_name.split()[0] if full_name.split() else ''
        user.last_name = ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else ''
        user.save()

        auth_login(request, user)
        messages.success(request, 'Account created successfully.')
        if role == 'hod':
            return redirect('hod_dashboard')
        elif role == 'teacher':
            return redirect('teacher_dashboard')
        return redirect('student_dashboard')

    return render(request, 'MyApp/signup.html')

def logout_view(request):
    auth_logout(request)
    return redirect('login')


@login_required
def profile_view(request):
    """Allow any logged-in user to update their first/last name and password.
    If password is changed, keep the session authenticated.
    """
    user = request.user
    if request.method == 'POST':
        first = request.POST.get('first_name', '').strip()
        last = request.POST.get('last_name', '').strip()
        pwd = request.POST.get('password', '')
        pwd2 = request.POST.get('password_confirm', '')

        if first:
            user.first_name = first
        if last:
            user.last_name = last

        if pwd:
            if pwd != pwd2:
                messages.error(request, 'Passwords do not match.')
                return redirect('profile')
            user.set_password(pwd)

        user.save()

        if pwd:
            # keep the user logged in after password change
            try:
                update_session_auth_hash(request, user)
            except Exception:
                pass

        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')

    return render(request, 'MyApp/profile.html', {'user_obj': user})

def student_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if getattr(request.user, 'role', '') != 'student':
        return redirect('teacher_dashboard')

    display_name = request.user.get_full_name() or request.user.username
    enrolled_courses = Course.objects.filter(enrollments__student=request.user).distinct()
    
    # Get messages sent to this student, newest first
    messages_qs = Message.objects.filter(recipient=request.user).order_by('-created_at')
    
    # DEBUG: Log message retrieval
    print(f"\n=== STUDENT DASHBOARD DEBUG ===")
    print(f"Student: {request.user.username}")
    print(f"Total messages for student: {messages_qs.count()}")
    for msg in messages_qs[:5]:
        print(f"  - From {msg.sender.username}: {msg.content[:50]}")

    # For each course, gather stats
    course_stats = []
    for course in enrolled_courses:
        assignments = course.assignments.filter(published=True)
        total_assignments = assignments.count()
        total_quizzes = assignments.filter(kind='quiz').count()
        total_homework = assignments.filter(kind='homework').count()
        total_projects = assignments.filter(kind='project').count()
        materials = course.materials.all()
        total_materials_for_course = materials.count()
        # Not yet submitted assignments/quizzes
        not_submitted = assignments.exclude(submissions__student=request.user).count()
        not_submitted_quiz = assignments.filter(kind='quiz').exclude(submissions__student=request.user).count()
        not_submitted_homework = assignments.filter(kind='homework').exclude(submissions__student=request.user).count()
        not_submitted_project = assignments.filter(kind='project').exclude(submissions__student=request.user).count()
        course_stats.append({
            'course': course,
            'total_assignments': total_assignments,
            'total_quizzes': total_quizzes,
            'total_homework': total_homework,
            'total_projects': total_projects,
            'total_materials': total_materials_for_course,
            'not_submitted': not_submitted,
            'not_submitted_quiz': not_submitted_quiz,
            'not_submitted_homework': not_submitted_homework,
            'not_submitted_project': not_submitted_project,
        })

    total_courses = enrolled_courses.count()
    total_materials = sum(stat['total_materials'] for stat in course_stats)
    total_remaining = sum(stat['not_submitted'] for stat in course_stats)

    return render(request, 'MyApp/student.html', {
        'display_name': display_name,
        'enrolled_courses': enrolled_courses,
        'student_messages': messages_qs,
        'course_stats': course_stats,
        'total_courses': total_courses,
        'total_materials': total_materials,
        'total_remaining': total_remaining,
    })

def teacher_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if getattr(request.user, 'role', '') != 'teacher':
        return redirect('student_dashboard')
    
    display_name = request.user.get_full_name() or request.user.username
    
    # Priority: Only show HOD assigned courses in teacher portal
    assigned_courses = request.user.assigned_courses.all()
    if assigned_courses.exists():
        teacher_courses = assigned_courses
    else:
        teacher_courses = Course.objects.filter(
            models.Q(teacher=request.user) |
            models.Q(assignments__created_by=request.user) | 
            models.Q(materials__uploaded_by=request.user)
        ).distinct()
    
    # Get all assignments created by this teacher
    assignments = Assignment.objects.filter(created_by=request.user).order_by('-created_at')
    
    # Get all materials uploaded by this teacher
    materials = Material.objects.filter(uploaded_by=request.user).order_by('-created_at')
    
    # Get students enrolled in teacher's courses
    total_students = Enrollment.objects.filter(
        course__in=teacher_courses
    ).values('student').distinct().count()
    
    # Count statistics
    total_assignments = assignments.count()
    total_materials = materials.count()
    published_assignments = assignments.filter(published=True).count()
    
    # Get total submissions for assignments
    total_submissions = Submission.objects.filter(
        assignment__created_by=request.user
    ).count()
    
    return render(request, 'MyApp/teacher.html', {
        'display_name': display_name,
        'user': request.user,
        'teacher_courses': teacher_courses,
        'assignments': assignments[:5],  # Show recent 5
        'materials': materials[:5],  # Show recent 5
        'total_students': total_students,
        'total_courses': teacher_courses.count(),
        'total_assignments': total_assignments,
        'total_materials': total_materials,
        'published_assignments': published_assignments,
        'total_submissions': total_submissions,
    })

def student_actions(request):
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'student':
        return redirect('login')

    enrolled_courses = Course.objects.filter(enrollments__student=request.user)
    assignments = Assignment.objects.filter(
        models.Q(course__in=enrolled_courses) | models.Q(assigned_student=request.user),
        published=True
    )
    
    unsubmitted = assignments.exclude(submissions__student=request.user)
    assignments_due = unsubmitted.exclude(kind='quiz').count()
    quizzes_scheduled = unsubmitted.filter(kind='quiz').count()
    
    materials = Material.objects.filter(course__in=enrolled_courses)
    materials_ready = materials.count()
    
    courses_active = enrolled_courses.count()
    
    latest_material = materials.order_by('-created_at').first()
    latest_assignment = assignments.order_by('-created_at').first()
    latest_update = "No updates yet"
    if latest_material and latest_assignment:
        if latest_material.created_at > latest_assignment.created_at:
            latest_update = f"New study notes: {latest_material.title}"
        else:
            latest_update = f"New assignment: {latest_assignment.title}"
    elif latest_material:
        latest_update = f"New study notes: {latest_material.title}"
    elif latest_assignment:
        latest_update = f"New assignment: {latest_assignment.title}"

    current_assignments_list = unsubmitted.order_by('-created_at')[:5]

    return render(request, 'MyApp/student-actions.html', {
        'assignments_due': assignments_due,
        'quizzes_scheduled': quizzes_scheduled,
        'materials_ready': materials_ready,
        'courses_active': courses_active,
        'readied_notes': materials_ready,
        'latest_update': latest_update,
        'current_assignments_list': current_assignments_list,
    })

def student_assignments(request):
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'student':
        return redirect('login')

    enrolled_courses = Course.objects.filter(enrollments__student=request.user)
    assignments = Assignment.objects.filter(
        models.Q(course__in=enrolled_courses) | models.Q(assigned_student=request.user),
        published=True
    ).order_by('-created_at')

    items = []
    completed_and_reviewed = []
    assignments_available = 0
    quizzes_live = 0
    pending_reviews = 0
    
    for a in assignments:
        sub = a.submissions.filter(student=request.user).first()
        items.append({'assignment': a, 'submission': sub})
        if a.kind == 'quiz':
            quizzes_live += 1
        else:
            assignments_available += 1
            
        if sub:
            if not sub.graded:
                pending_reviews += 1
            else:
                completed_and_reviewed.append(sub)

    materials = Material.objects.filter(course__in=enrolled_courses)
    material_packs = materials.count()

    return render(request, 'MyApp/student-assignments.html', {
        'items': items,
        'assignments_available': assignments_available,
        'quizzes_live': quizzes_live,
        'pending_reviews': pending_reviews,
        'material_packs': material_packs,
        'completed_and_reviewed': completed_and_reviewed,
    })

def student_materials(request):
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'student':
        return redirect('login')

    from django.utils import timezone

    enrolled_courses = Course.objects.filter(enrollments__student=request.user)
    materials = Material.objects.filter(course__in=enrolled_courses).order_by('-created_at')
    
    regular_materials = materials.exclude(description='past_paper')
    past_papers = materials.filter(description='past_paper')
    
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = materials.filter(created_at__gte=today_start).count()

    return render(request, 'MyApp/student-materials.html', {
        'materials': materials,
        'regular_materials': regular_materials,
        'past_papers': past_papers,
        'material_packs': regular_materials.count(),
        'past_papers_count': past_papers.count(),
        'new_today': new_today,
    })


def student_pastpapers(request):
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'student':
        return redirect('login')

    enrolled_courses = Course.objects.filter(enrollments__student=request.user)
    materials = Material.objects.filter(course__in=enrolled_courses, description='past_paper').order_by('-created_at')
    return render(request, 'MyApp/student-pastpapers.html', {'materials': materials})


def student_progress(request):
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'student':
        return redirect('login')

    enrolled_courses = Course.objects.filter(enrollments__student=request.user)
    assignments = Assignment.objects.filter(course__in=enrolled_courses, published=True)
    total_published = assignments.count()
    
    submissions = Submission.objects.filter(student=request.user, assignment__in=assignments)
    submitted_count = submissions.count()
    
    completion_rate = int((submitted_count / total_published * 100)) if total_published > 0 else 100
    tasks_remaining = total_published - submitted_count
    
    course_progress = []
    for course in enrolled_courses:
        course_assignments = assignments.filter(course=course)
        c_total = course_assignments.count()
        c_submitted = submissions.filter(assignment__course=course).count()
        c_pct = int((c_submitted / c_total * 100)) if c_total > 0 else 100
        
        status = "Excellent"
        if c_pct < 50:
            status = "Needs attention"
        elif c_pct < 80:
            status = "Moderate"
        else:
            status = "High"
            
        course_progress.append({
            'course': course,
            'completion_pct': c_pct,
            'status': status,
        })
        
    finish_goals = assignments.exclude(submissions__student=request.user).order_by('created_at')[:5]

    return render(request, 'MyApp/student-progress.html', {
        'completion_rate': completion_rate,
        'courses_active': enrolled_courses.count(),
        'tasks_remaining': tasks_remaining,
        'course_progress': course_progress,
        'finish_goals': finish_goals,
    })

def student_quiz(request):
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'student':
        return redirect('login')

    enrolled_courses = Course.objects.filter(enrollments__student=request.user).distinct()
    
    quizzes = Assignment.objects.filter(
        published=True,
        kind='quiz'
    ).filter(
        models.Q(course__in=enrolled_courses, assigned_student__isnull=True) | models.Q(assigned_student=request.user)
    ).order_by('-created_at')
    
    submitted_quizzes_ids = Submission.objects.filter(
        student=request.user, 
        assignment__in=quizzes
    ).values_list('assignment_id', flat=True)
    
    upcoming_quizzes = quizzes.exclude(id__in=submitted_quizzes_ids)
    completed_quizzes = []
    for quiz in quizzes.filter(id__in=submitted_quizzes_ids):
        submission = quiz.submissions.filter(student=request.user).first()
        completed_quizzes.append({
            'quiz': quiz,
            'submission': submission,
        })
    
    due_soon_count = upcoming_quizzes.count()

    return render(request, 'MyApp/student-quiz.html', {
        'quizzes_available_count': upcoming_quizzes.count(),
        'due_soon_count': due_soon_count,
        'completed_count': len(completed_quizzes),
        'upcoming_quizzes': upcoming_quizzes,
        'completed_quizzes': completed_quizzes,
    })

def student_results(request):
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'student':
        return redirect('login')

    submissions = Submission.objects.filter(student=request.user, graded=True).order_by('-submitted_at')
    
    quizzes_graded_count = submissions.filter(assignment__kind='quiz').count()
    assignments_graded_count = submissions.exclude(assignment__kind='quiz').count()
    
    marks_list = [sub.marks for sub in submissions if sub.marks is not None]
    average_score = int(sum(marks_list) / len(marks_list)) if marks_list else 0

    latest_feedback = submissions[:5]

    return render(request, 'MyApp/student-results.html', {
        'quizzes_graded_count': quizzes_graded_count,
        'assignments_graded_count': assignments_graded_count,
        'average_score': average_score,
        'latest_feedback': latest_feedback,
    })

def teacher_actions(request):
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        return redirect('login')

    display_name = request.user.get_full_name() or request.user.username

    assigned_courses = request.user.assigned_courses.all()
    if assigned_courses.exists():
        teacher_courses = assigned_courses
    else:
        teacher_courses = Course.objects.filter(
            models.Q(teacher=request.user) |
            models.Q(assignments__created_by=request.user) | 
            models.Q(materials__uploaded_by=request.user)
        ).distinct()

    course_actions_count = teacher_courses.count()
    quick_tools_count = 6
    
    department_reach = Enrollment.objects.filter(course__in=teacher_courses).values('student').distinct().count()

    recent_assignments = Assignment.objects.filter(created_by=request.user).order_by('-created_at')[:3]
    recent_materials = Material.objects.filter(uploaded_by=request.user).order_by('-created_at')[:3]
    
    activities = []
    for a in recent_assignments:
        activities.append({
            'title': f"Assignment created: {a.title}",
            'meta': f"{a.course.name} - {a.get_kind_display()}",
            'time': a.created_at,
            'desc': a.description or "No description"
        })
    for m in recent_materials:
        is_pp = "Past Paper" if m.description == 'past_paper' else "Study Notes"
        activities.append({
            'title': f"{is_pp} uploaded: {m.title}",
            'meta': f"{m.course.name}",
            'time': m.created_at,
            'desc': m.description if m.description != 'past_paper' else "Past exam paper published."
        })
    
    activities.sort(key=lambda x: x['time'], reverse=True)
    latest_activities = activities[:3]
    
    # Get all teacher resources
    past_papers = Material.objects.filter(uploaded_by=request.user, description='past_paper').order_by('-created_at')
    assignments = Assignment.objects.filter(created_by=request.user).order_by('-created_at')
    materials = Material.objects.filter(uploaded_by=request.user).exclude(description='past_paper').order_by('-created_at')
    invitations = Invitation.objects.filter(sender=request.user).order_by('-created_at')

    return render(request, 'MyApp/teacher-actions.html', {
        'display_name': display_name,
        'user': request.user,
        'course_actions_count': course_actions_count,
        'quick_tools_count': quick_tools_count,
        'department_reach': department_reach,
        'latest_activities': latest_activities,
        'teacher_courses': teacher_courses,
        'past_papers': past_papers,
        'assignments': assignments,
        'materials': materials,
        'invitations': invitations,
    })

@login_required
@never_cache
@ensure_csrf_cookie
@csrf_protect
def teacher_assignment(request):
    # Only teachers allowed
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')

    if request.method == 'POST':
        from datetime import datetime

        form_type = request.POST.get('form_type', 'assignment')
        course_name = request.POST.get('course')
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        uploaded_file = request.FILES.get('file')
        publish = bool(request.POST.get('publish'))
        deadline = None
        deadline_raw = request.POST.get('deadline')
        if deadline_raw:
            try:
                deadline = datetime.fromisoformat(deadline_raw)
                if timezone.is_naive(deadline):
                    deadline = timezone.make_aware(deadline, timezone.get_current_timezone())
            except ValueError:
                deadline = None

        if not course_name or not title:
            messages.error(request, 'Please provide course and title.')
            return redirect('teacher_assignment')

        assigned_courses = request.user.assigned_courses.all()
        if assigned_courses.exists() and not assigned_courses.filter(name=course_name).exists():
            assigned_names = ', '.join([c.name for c in assigned_courses])
            messages.error(request, f"Access Denied: You can only create coursework for courses assigned to you by the HOD ({assigned_names}).")
            return redirect('teacher_assignment')

        course_obj, _ = Course.objects.get_or_create(name=course_name, defaults={'teacher': request.user})

        if form_type == 'quiz':
            quiz_type = request.POST.get('quiz_type', 'manual')
            student_id = request.POST.get('assigned_student')
            assigned_student = None
            
            # DEBUG: Log publish checkbox status
            publish_raw = request.POST.get('publish')
            print(f"\n=== QUIZ DEBUG ===")
            print(f"publish_raw from POST: {repr(publish_raw)}")
            print(f"publish boolean: {publish}")
            
            if student_id:
                assigned_student = CustomUser.objects.filter(id=student_id, role='student').first()
                if assigned_student and not Enrollment.objects.filter(student=assigned_student, course=course_obj).exists():
                    assigned_student = None

            assignment = Assignment.objects.create(
                title=title,
                kind='quiz',
                description=description,
                course=course_obj,
                created_by=request.user,
                published=publish,
                file=uploaded_file,
                quiz_type=quiz_type,
                assigned_student=assigned_student,
                deadline=deadline,
            )
            
            # DEBUG: Verify assignment was created with published flag
            print(f"Assignment created: ID={assignment.id}, published={assignment.published}")
            assignment_check = Assignment.objects.get(id=assignment.id)
            print(f"Assignment from DB: published={assignment_check.published}")

            if publish:
                notification_text = f"New quiz '{assignment.title}' is now available for {course_obj.name}. Start the quiz when ready."
                try:
                    if assigned_student:
                        msg = Message.objects.create(
                            sender=request.user,
                            recipient=assigned_student,
                            course=course_obj,
                            content=notification_text,
                        )
                        print(f"Created message to {assigned_student.username}: {msg.id}")
                    else:
                        enrolled_students = CustomUser.objects.filter(
                            role='student',
                            enrollments__course=course_obj,
                        ).distinct()
                        print(f"Enrolled students count: {enrolled_students.count()}")
                        for student in enrolled_students:
                            msg = Message.objects.create(
                                sender=request.user,
                                recipient=student,
                                course=course_obj,
                                content=notification_text,
                            )
                            print(f"Created message to {student.username}: {msg.id}")
                except Exception as e:
                    import traceback
                    print(f"Notification error: {e}")
                    traceback.print_exc()

            question_count = int(request.POST.get('question_count', '0'))
            for index in range(question_count):
                question_text = request.POST.get(f'question_text_{index}', '').strip()
                if not question_text:
                    continue
                if quiz_type == 'manual':
                    expected_answer = request.POST.get(f'question_answer_{index}', '').strip()
                    QuizQuestion.objects.create(
                        assignment=assignment,
                        question_text=question_text,
                        question_type='manual',
                        expected_answer=expected_answer,
                        order=index,
                    )
                elif quiz_type == 'mcq':
                    options = {
                        'A': request.POST.get(f'question_option_{index}_A', '').strip(),
                        'B': request.POST.get(f'question_option_{index}_B', '').strip(),
                        'C': request.POST.get(f'question_option_{index}_C', '').strip(),
                        'D': request.POST.get(f'question_option_{index}_D', '').strip(),
                    }
                    correct_choice = request.POST.get(f'question_correct_{index}', '').strip()
                    QuizQuestion.objects.create(
                        assignment=assignment,
                        question_text=question_text,
                        question_type='mcq',
                        options=options,
                        expected_answer=correct_choice,
                        order=index,
                    )
                else:
                    blanks = parse_fill_in_blanks(question_text)
                    expected_answer = request.POST.get(f'question_answer_{index}', '').strip()
                    QuizQuestion.objects.create(
                        assignment=assignment,
                        question_text=question_text,
                        question_type='fillblank',
                        blanks=blanks,
                        expected_answer=expected_answer,
                        order=index,
                    )

            if publish:
                messages.success(request, f'Quiz "{assignment.title}" published! Students enrolled in {course_obj.name} will be notified.')
            else:
                messages.success(request, f'Quiz "{assignment.title}" saved as draft. Publish it when ready.')
            return redirect('teacher_assignment')

        kind = request.POST.get('kind', 'homework')
        assignment = Assignment.objects.create(
            title=title,
            kind=kind,
            description=description,
            course=course_obj,
            created_by=request.user,
            published=publish,
            file=uploaded_file,
            deadline=deadline,
        )
        messages.success(request, 'Assignment created and published.' if publish else 'Assignment saved as draft.')
        return redirect('teacher_assignment')

    from django.db.models import Count

    my_assignments = Assignment.objects.filter(created_by=request.user)
    assignments_uploaded_count = my_assignments.count()
    quizzes_published_count = my_assignments.filter(kind='quiz', published=True).count()
    pending_review_count = Submission.objects.filter(assignment__created_by=request.user, graded=False).count()
    
    last_assignment = my_assignments.order_by('-created_at').first()
    last_upload_time = last_assignment.created_at if last_assignment else None

    focus_course = my_assignments.values('course__name').annotate(num_assignments=Count('id')).order_by('-num_assignments').first()
    course_focus = focus_course['course__name'] if focus_course else "N/A"

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_assignments = my_assignments.filter(created_at__gte=today_start).count()
    today_materials = Material.objects.filter(uploaded_by=request.user, created_at__gte=today_start).count()
    today_actions_count = today_assignments + today_materials

    assigned_courses = request.user.assigned_courses.all()
    courses = assigned_courses if assigned_courses.exists() else Course.objects.all()
    students = CustomUser.objects.filter(role='student', enrollments__course__in=courses).distinct().prefetch_related('enrollments__course').order_by('first_name', 'last_name', 'username')
    teacher_assignments = Assignment.objects.filter(created_by=request.user).order_by('-created_at')
    get_token(request)
    return render(request, 'MyApp/teacher-assignment.html', {
        'courses': courses,
        'students': students,
        'teacher_assignments': teacher_assignments,
        'assignments_uploaded_count': assignments_uploaded_count,
        'quizzes_published_count': quizzes_published_count,
        'pending_review_count': pending_review_count,
        'last_upload_time': last_upload_time,
        'course_focus': course_focus,
        'today_actions_count': today_actions_count,
    })


@login_required
def teacher_submissions(request, assignment_id):
    """Allow a teacher to view all submissions for a specific assignment."""
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')
    try:
        assignment = Assignment.objects.get(id=assignment_id, created_by=request.user)
    except Assignment.DoesNotExist:
        messages.error(request, 'Assignment not found.')
        return redirect('teacher_assignment')

    submissions = Submission.objects.filter(assignment=assignment).select_related('student')
    questions_dict = {str(q.id): q for q in assignment.quiz_questions.all()}
    for sub in submissions:
        if sub.answers and isinstance(sub.answers, dict):
            formatted = []
            for q_id, ans in sub.answers.items():
                q_obj = questions_dict.get(str(q_id))
                ans_str = ans if isinstance(ans, str) else (', '.join(ans) if isinstance(ans, list) else str(ans))
                expected = q_obj.expected_answer if q_obj else ''
                q_text = q_obj.question_text if q_obj else f'Question {q_id}'
                is_manual = bool(q_obj and q_obj.question_type == 'manual')
                is_correct = None
                if expected and not is_manual:
                    is_correct = (ans_str.strip().lower() == expected.strip().lower())
                formatted.append({
                    'question_text': q_text,
                    'student_answer': ans_str,
                    'expected_answer': expected,
                    'is_correct': is_correct,
                    'is_manual': is_manual,
                })
            sub.formatted_answers = formatted

    if request.method == 'POST':
        for sub in submissions:
            marks_val = request.POST.get(f'marks_{sub.id}')
            grade_val = request.POST.get(f'grade_{sub.id}', '')
            feedback_val = request.POST.get(f'feedback_{sub.id}', '')
            if marks_val is not None and marks_val != '':
                try:
                    sub.marks = float(marks_val)
                except ValueError:
                    sub.marks = None
            else:
                sub.marks = None
            sub.grade = grade_val
            sub.feedback = feedback_val
            sub.graded = bool(grade_val or feedback_val or sub.marks is not None)
            sub.save()

        messages.success(request, 'Submission scores and feedback saved successfully.')
        return redirect('teacher_submissions', assignment_id=assignment.id)

    return render(request, 'MyApp/teacher-submissions.html', {
        'assignment': assignment,
        'submissions': submissions,
    })



@login_required
def submit_assignment(request, assignment_id):
    try:
        assignment = Assignment.objects.get(id=assignment_id)
    except Assignment.DoesNotExist:
        messages.error(request, 'Assignment not found.')
        return redirect('student_assignments')

    # allow direct student assignment even when the student is not enrolled in the course
    if assignment.assigned_student != request.user:
        if not Enrollment.objects.filter(student=request.user, course=assignment.course).exists():
            messages.error(request, 'You are not enrolled in this course.')
            return redirect('student_assignments')

    from django.utils import timezone

    # Single-attempt quiz constraint: If student already submitted, do not allow re-entry
    if assignment.kind == 'quiz':
        existing_sub = Submission.objects.filter(assignment=assignment, student=request.user).first()
        if existing_sub:
            messages.info(request, f"You have already attempted and submitted the quiz '{assignment.title}'. Multiple attempts are strictly prohibited.")
            return redirect('student_assignments')

    if request.method == 'POST':
        is_auto = request.POST.get('auto_submitted') == 'true'
        reason = request.POST.get('submission_reason') or 'Automated submission on exam exit / tab switch'

        sub, created = Submission.objects.get_or_create(assignment=assignment, student=request.user)
        if assignment.kind == 'quiz':
            if assignment.quiz_questions.exists():
                answers = {}
                for question in assignment.quiz_questions.all():
                    if question.question_type == 'fillblank':
                        blank_values = []
                        blanks = question.blanks or parse_fill_in_blanks(question.question_text)
                        for blank_index in range(len(blanks) if blanks else 1):
                            blank_field = f'question_{question.id}_blank_{blank_index}'
                            blank_values.append(request.POST.get(blank_field, '').strip())
                        answers[str(question.id)] = blank_values
                    else:
                        field_name = f'question_{question.id}'
                        answer_value = request.POST.get(field_name, '').strip()
                        answers[str(question.id)] = answer_value
                sub.answers = answers
                sub.answer_text = request.POST.get('answer_text', '').strip()
            else:
                sub.answer_text = request.POST.get('answer_text', '').strip()

            if is_auto:
                sub.feedback = f"[Proctoring Security Alert] {reason} at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}."
                messages.warning(request, f"Examination Integrity Notice: {reason}. Your quiz answers have been locked and submitted.")
            else:
                messages.success(request, f"Quiz '{assignment.title}' submitted successfully.")

            sub.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                return JsonResponse({'status': 'ok', 'auto_submitted': is_auto, 'message': 'Quiz submitted'})
            return redirect('student_assignments')

        else:
            uploaded = request.FILES.get('file')
            answer_text = request.POST.get('answer_text', '').strip()
            if not uploaded and not answer_text and not sub.file and not sub.answer_text:
                messages.error(request, 'Please provide an answer or attach a file.')
                deadline_passed = bool(assignment.deadline and timezone.now() > assignment.deadline)
                return render(request, 'MyApp/submit-assignment.html', {
                    'assignment': assignment,
                    'deadline_passed': deadline_passed,
                })
            if uploaded:
                sub.file = uploaded
            if answer_text:
                sub.answer_text = answer_text
            sub.save()
            messages.success(request, 'Submission uploaded successfully.')
            return redirect('student_assignments')

    deadline_passed = False
    if assignment.deadline and timezone.now() > assignment.deadline:
        deadline_passed = True

    return render(request, 'MyApp/submit-assignment.html', {
        'assignment': assignment,
        'deadline_passed': deadline_passed,
    })


@login_required
def teacher_detect(request):
    """Allow a teacher to upload a file (assignment, quiz, etc.) and get AI detection result."""
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')
    result = None
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        # Save to a temporary location
        import tempfile, os
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        try:
            from .utils.detector import predict
            result = predict(tmp_path)
        except Exception as e:
            messages.error(request, f'Error during detection: {e}')
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass
    return render(request, 'MyApp/teacher-detect.html', {'result': result})


@login_required
def detect_submission(request, submission_id):
    """Detect if a student submission is AI-generated or human-written."""
    from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
    import tempfile
    import os
    
    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST requests are allowed.')
    
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        return HttpResponseForbidden('Only teachers can use this endpoint.')
    
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        return HttpResponseBadRequest('Submission not found.')
    
    # Check if submission has either file or text or answers
    if not submission.file and not submission.answer_text and not submission.answers:
        return HttpResponseBadRequest('Submission has no file or text to analyze.')
    
    # Validate teacher access to this submission
    if submission.assignment.created_by != request.user:
        return HttpResponseForbidden('You do not have permission to check this submission.')
    
    try:
        from .utils.detector import predict
        
        if submission.file:
            # Validate file extension
            import os
            file_name = submission.file.name
            file_ext = os.path.splitext(file_name)[1].lower()
            
            ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.pptx', '.txt'}
            if file_ext not in ALLOWED_EXTENSIONS:
                return JsonResponse({'error': f'File type {file_ext} is not supported for detection.'}, status=400)
            
            # Save to temporary location and detect
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                submission.file.seek(0)
                tmp.write(submission.file.read())
                tmp_path = tmp.name
            
            try:
                result = predict(tmp_path)
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        
        elif submission.answer_text:
            # Analyze text submission
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp:
                tmp.write(submission.answer_text)
                tmp_path = tmp.name
            
            try:
                result = predict(tmp_path)
            finally:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except OSError:
                    pass
        else:
            # Analyze quiz answers
            text_lines = []
            for q_id, ans in (submission.answers or {}).items():
                ans_str = ans if isinstance(ans, str) else (', '.join(ans) if isinstance(ans, list) else str(ans))
                text_lines.append(ans_str)
            content_str = '\n\n'.join(text_lines) or 'No answer text'
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp:
                tmp.write(content_str)
                tmp_path = tmp.name
            
            try:
                result = predict(tmp_path)
            finally:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except OSError:
                    pass
        
        return JsonResponse(result)
    
    except Exception as e:
        return JsonResponse({'error': f'Detection failed: {str(e)}'}, status=500)


@login_required
def teacher_materials(request):
    """Allow a teacher to upload materials and view uploaded materials list."""
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')

    if request.method == 'POST' and request.FILES.get('file'):
        course_name = request.POST.get('course')
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        uploaded_file = request.FILES.get('file')

        if not course_name or not title or not uploaded_file:
            messages.error(request, 'Please provide course, title and select a file to upload.')
            return redirect('teacher_materials')

        assigned_courses = request.user.assigned_courses.all()
        if assigned_courses.exists() and not assigned_courses.filter(name=course_name).exists():
            assigned_names = ', '.join([c.name for c in assigned_courses])
            messages.error(request, f"Access Denied: You can only upload materials for courses assigned to you by the HOD ({assigned_names}).")
            return redirect('teacher_materials')

        # Save file directly without compression
        original_size = uploaded_file.size

        # Get or create the course
        course_obj, _ = Course.objects.get_or_create(name=course_name, defaults={'teacher': request.user})
        Material.objects.create(
            title=title,
            course=course_obj,
            uploaded_by=request.user,
            file=uploaded_file,
            description=description,
        )

        messages.success(request, f'Material published successfully! File size: {original_size / (1024*1024):.2f} MB')
        return redirect('teacher_materials')

    # GET: display materials list
    materials = Material.objects.filter(uploaded_by=request.user).order_by('-created_at')
    assigned_courses = request.user.assigned_courses.all()
    courses = assigned_courses if assigned_courses.exists() else Course.objects.all()
    teacher_courses = assigned_courses if assigned_courses.exists() else Course.objects.filter(
        models.Q(teacher=request.user) |
        models.Q(assignments__created_by=request.user) |
        models.Q(materials__uploaded_by=request.user)
    ).distinct()
    total_files = materials.count()
    def _get_m_size(m):
        try:
            return m.file.size if (m.file and m.file.name) else 0
        except Exception:
            return 0
    total_bytes = sum(_get_m_size(m) for m in materials)
    if total_bytes < 1024:
        storage_used = f"{total_bytes} B"
    elif total_bytes < 1024 * 1024:
        storage_used = f"{total_bytes / 1024:.1f} KB"
    elif total_bytes < 1024 * 1024 * 1024:
        storage_used = f"{total_bytes / (1024 * 1024):.1f} MB"
    else:
        storage_used = f"{total_bytes / (1024 * 1024 * 1024):.1f} GB" 
    student_count = Enrollment.objects.filter(course__in=teacher_courses).values('student').distinct().count()
    downloads = student_count * total_files * 3

    return render(request, 'MyApp/teacher-materials.html', {
        'materials': materials,
        'courses': courses,
        'total_files': total_files,
        'storage_used': storage_used,
        'downloads': downloads,
    })

import uuid
# pyrefly: ignore [missing-import]
from django.core.mail import send_mail
# pyrefly: ignore [missing-import]
from django.conf import settings
# pyrefly: ignore [missing-import]
from django.urls import reverse
# pyrefly: ignore [missing-import]
from .models import Invitation, CustomUser, Course, Enrollment, Assignment, Material

@login_required
def teacher_invite(request):
    # Manual student invite & HOD Excel Roster Upload
    # Supports selecting 1 course, multiple courses, or all assigned courses
    if not hasattr(request.user, 'role') or request.user.role != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')

    assigned_courses = request.user.assigned_courses.all()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'edit_student':
            student_id = request.POST.get('student_id')
            target_student = CustomUser.objects.filter(id=student_id, role='student').first()
            if not target_student:
                messages.error(request, 'Student record not found.')
                return redirect('teacher_invite')

            new_username = request.POST.get('username', '').strip()
            new_password = request.POST.get('password', '').strip()
            full_name = request.POST.get('full_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone_number', '').strip()
            course_id = request.POST.get('course_id')

            if new_username and new_username != target_student.username:
                if CustomUser.objects.filter(username=new_username).exclude(id=target_student.id).exists():
                    messages.error(request, f"Student Roll / Username '{new_username}' is already taken.")
                    return redirect('teacher_invite')
                target_student.username = new_username

            if new_password:
                target_student.set_password(new_password)

            if full_name:
                parts = full_name.split(None, 1)
                target_student.first_name = parts[0]
                target_student.last_name = parts[1] if len(parts) > 1 else ''

            if email is not None:
                target_student.email = email
            if phone is not None:
                target_student.phone_number = phone

            target_student.save()

            if course_id:
                new_c = Course.objects.filter(id=course_id).first()
                if new_c:
                    Enrollment.objects.get_or_create(student=target_student, course=new_c)

            messages.success(request, f"Student '{target_student.username}' record updated successfully.")
            return redirect('teacher_invite')

        elif action == 'delete_student':
            student_id = request.POST.get('student_id')
            course_id = request.POST.get('course_id')
            target_student = CustomUser.objects.filter(id=student_id, role='student').first()
            if not target_student:
                messages.error(request, 'Student not found.')
                return redirect('teacher_invite')

            if course_id:
                Enrollment.objects.filter(student=target_student, course_id=course_id).delete()
                messages.success(request, f"Student '{target_student.username}' unenrolled from course.")
            else:
                Enrollment.objects.filter(student=target_student).delete()
                target_student.delete()
                messages.success(request, f"Student '{target_student.username}' removed from platform.")
            return redirect('teacher_invite')

        selected_courses_list = request.POST.getlist('selected_courses')
        primary_course = request.POST.get('course_name') or request.POST.get('course')
        course_code = request.POST.get('course_code') or request.POST.get('course_id')
        students_text = request.POST.get('students')
        single_roll = request.POST.get('student_roll')
        single_pass = request.POST.get('student_password')
        single_name = request.POST.get('student_name')
        roster_file = request.FILES.get('roster_file')
        all_courses_flag = (
            request.POST.get('all_courses') == '1' or 
            'all' in selected_courses_list or 
            primary_course == 'all' or 
            primary_course == '__ALL__'
        )

        chosen_courses = []
        if all_courses_flag:
            if assigned_courses.exists():
                chosen_courses = list(assigned_courses)
            else:
                chosen_courses = list(Course.objects.filter(teacher=request.user))
                if not chosen_courses and primary_course and primary_course not in ['all', '__ALL__']:
                    c_obj, _ = Course.objects.get_or_create(name=primary_course, defaults={'teacher': request.user})
                    chosen_courses = [c_obj]
        else:
            candidates = []
            if primary_course and primary_course not in ['all', '__ALL__']:
                candidates.append(primary_course)
            for sc in selected_courses_list:
                if sc and sc not in ['all', '__ALL__'] and sc not in candidates:
                    candidates.append(sc)

            for c_val in candidates:
                c_val = str(c_val).strip()
                if not c_val:
                    continue
                c_obj = None
                if c_val.isdigit():
                    c_obj = Course.objects.filter(id=int(c_val)).first()
                if not c_obj:
                    c_obj = Course.objects.filter(name=c_val).first()
                if not c_obj and not assigned_courses.exists():
                    c_obj, _ = Course.objects.get_or_create(name=c_val, defaults={'code': course_code or '', 'teacher': request.user})
                if c_obj:
                    if assigned_courses.exists() and not assigned_courses.filter(id=c_obj.id).exists():
                        continue
                    if c_obj not in chosen_courses:
                        chosen_courses.append(c_obj)

        if not chosen_courses:
            if assigned_courses.exists():
                assigned_names = ', '.join([c.name for c in assigned_courses])
                messages.error(request, f"Access Denied: Please select one or more courses assigned to you by the HOD ({assigned_names}).")
            else:
                messages.error(request, 'Please select or provide a course name.')
            return redirect('teacher_invite')

        entries = []

        # Handle HOD Roster File Upload (Excel CSV)
        if roster_file:
            import csv
            import io
            file_data = roster_file.read()
            try:
                decoded = file_data.decode('utf-8')
            except UnicodeDecodeError:
                decoded = file_data.decode('latin-1', errors='ignore')

            reader = csv.reader(io.StringIO(decoded))
            header = None
            for row in reader:
                if not row or not any(row):
                    continue
                # Detect header row
                if header is None and any('student' in str(c).lower() or 'roll' in str(c).lower() or 'id' in str(c).lower() for c in row):
                    header = [c.strip().lower() for c in row]
                    continue

                if header:
                    row_dict = {}
                    for idx, val in enumerate(row):
                        if idx < len(header):
                            row_dict[header[idx]] = val.strip()
                    roll = row_dict.get('student_id') or row_dict.get('student id') or row_dict.get('roll') or row_dict.get('roll_no') or (row[0].strip() if len(row) > 0 else '')
                    pwd = row_dict.get('password') or (row[1].strip() if len(row) > 1 and row[1].strip() else 'bgnu1234')
                    name = row_dict.get('full_name') or row_dict.get('full name') or row_dict.get('name') or (row[2].strip() if len(row) > 2 else '')
                    email = row_dict.get('email') or (row[3].strip() if len(row) > 3 else '')
                    phone = row_dict.get('phone_number') or row_dict.get('phone') or (row[4].strip() if len(row) > 4 else '')
                    if roll:
                        entries.append((roll, pwd, name, email, phone))
                else:
                    roll = row[0].strip() if len(row) > 0 else ''
                    pwd = row[1].strip() if len(row) > 1 and row[1].strip() else 'bgnu1234'
                    name = row[2].strip() if len(row) > 2 else ''
                    email = row[3].strip() if len(row) > 3 else ''
                    phone = row[4].strip() if len(row) > 4 else ''
                    if roll:
                        entries.append((roll, pwd, name, email, phone))

        elif students_text:
            for line in students_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 2:
                    messages.error(request, f"Invalid line format: '{line}'. Use 'roll,password' or 'roll,password,Full Name'.")
                    continue
                roll = parts[0]
                pwd = parts[1]
                name = parts[2] if len(parts) >= 3 else ''
                entries.append((roll, pwd, name, '', ''))
        elif single_roll and single_pass:
            entries.append((single_roll.strip(), single_pass.strip(), single_name.strip() if single_name else '', '', ''))
        else:
            messages.error(request, 'Please provide student details or upload the HOD roster sheet.')
            return redirect('teacher_invite')

        created = 0
        enrolled = 0

        if chosen_courses:
            try:
                request.session['last_course_id'] = chosen_courses[0].id
            except Exception:
                pass

        for entry in entries:
            roll = entry[0]
            pwd = entry[1]
            name = entry[2] if len(entry) > 2 else ''
            email = entry[3] if len(entry) > 3 else ''
            phone = entry[4] if len(entry) > 4 else ''
            if not roll or not pwd:
                continue
            try:
                user, was_created = CustomUser.objects.get_or_create(
                    username=roll,
                    defaults={'role': 'student', 'email': email, 'phone_number': phone}
                )
                user.set_password(pwd)
                user.role = 'student'
                if email and not user.email:
                    user.email = email
                if phone and not user.phone_number:
                    user.phone_number = phone
                if name:
                    parts = name.split(None, 1)
                    user.first_name = parts[0]
                    user.last_name = parts[1] if len(parts) > 1 else ''
                user.save()
                if was_created:
                    created += 1

                for course_obj in chosen_courses:
                    enroll_obj, enroll_created = Enrollment.objects.get_or_create(student=user, course=course_obj)
                    if enroll_created:
                        enrolled += 1
            except Exception:
                continue

        source_info = "HOD roster sheet" if roster_file else "form submission"
        course_names_str = ', '.join([c.name for c in chosen_courses])
        messages.success(request, f"Processed {source_info}: created {created} new accounts, enrolled students into {course_names_str}.")
        return redirect('teacher_invite')

    teacher_courses = assigned_courses if assigned_courses.exists() else Course.objects.all()

    last_course = None
    recent_enrollments = []
    course_name_prefill = ''
    course_code_prefill = ''
    last_course_id = request.session.get('last_course_id')
    if last_course_id:
        try:
            last_course = Course.objects.filter(id=last_course_id).first()
        except Exception:
            last_course = None

    if not last_course and teacher_courses.exists():
        last_course = teacher_courses.first()

    if last_course:
        course_name_prefill = last_course.name
        course_code_prefill = last_course.code or ''
        recent_enrollments = Enrollment.objects.select_related('student', 'course').filter(course__in=teacher_courses).order_by('-enrolled_at')[:40]
    else:
        recent_enrollments = Enrollment.objects.select_related('student', 'course').all().order_by('-enrolled_at')[:40]

    return render(request, 'MyApp/teacher-invite.html', {
        'last_course': last_course,
        'course_name_prefill': course_name_prefill,
        'course_code_prefill': course_code_prefill,
        'recent_enrollments': recent_enrollments,
        'invitations': Invitation.objects.filter(sender=request.user),
        'assigned_courses': assigned_courses,
        'teacher_courses': teacher_courses,
    })

def accept_invite(request, token):
    # Accept-invite flow has been disabled.
    messages.info(request, "Invitation acceptance is disabled.")
    return redirect('login')


@login_required
def teacher_material_detect(request, material_id):
    """Detect whether a uploaded material was AI‑generated or human created."""
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')
    try:
        material = Material.objects.get(id=material_id, uploaded_by=request.user)
    except Material.DoesNotExist:
        messages.error(request, 'Material not found.')
        return redirect('teacher_materials')
    if not material.file or not material.file.name:
        messages.error(request, 'No file attached to this material.')
        return redirect('teacher_materials')

    try:
        if not hasattr(material.file, 'path') or not os.path.exists(material.file.path):
            messages.error(request, 'The attached file is not present on the server storage.')
            return redirect('teacher_materials')
        file_path = material.file.path
        from .utils.detector import predict
        result = predict(file_path)
    except Exception as e:
        messages.error(request, f'Detection error: {e}')
        return redirect('teacher_materials')
    return render(request, 'MyApp/teacher-material-detect.html', {
        'material': material,
        'result': result,
    })

# Duplicate material upload block removed


def teacher_pastpaper(request):
    # Only teachers allowed
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')

    if request.method == 'POST':
        course_name = request.POST.get('course')
        title = request.POST.get('title')
        uploaded_file = request.FILES.get('file')

        if not course_name or not title or not uploaded_file:
            messages.error(request, 'Please provide course, title and select a file to upload.')
            return redirect('teacher_pastpaper')

        assigned_courses = request.user.assigned_courses.all()
        if assigned_courses.exists() and not assigned_courses.filter(name=course_name).exists():
            assigned_names = ', '.join([c.name for c in assigned_courses])
            messages.error(request, f"Access Denied: You can only publish past papers for courses assigned to you by the HOD ({assigned_names}).")
            return redirect('teacher_pastpaper')

        # Save file directly without compression
        original_name = uploaded_file.name
        original_size = uploaded_file.size

        # Get or create the course
        course_obj, created = Course.objects.get_or_create(name=course_name, defaults={'teacher': request.user})
        
        # Create Material object for past paper
        Material.objects.create(
            title=title,
            course=course_obj,
            uploaded_by=request.user,
            file=uploaded_file,
            description='past_paper'
        )

        messages.success(request, f'Past paper "{title}" published successfully! File size: {original_size / (1024*1024):.2f} MB')
        return redirect('teacher_pastpaper')

    # GET - Display upload form and list of past papers (only HOD assigned courses)
    assigned_courses = request.user.assigned_courses.all()
    courses = assigned_courses if assigned_courses.exists() else Course.objects.all()
    materials = Material.objects.filter(uploaded_by=request.user, description='past_paper').order_by('-created_at')
    return render(request, 'MyApp/teacher-pastpaper.html', {'courses': courses, 'materials': materials})


@login_required
def delete_pastpaper(request, material_id):
    """Delete a past paper uploaded by the teacher."""
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')
    
    try:
        material = Material.objects.get(id=material_id, uploaded_by=request.user, description='past_paper')
        paper_title = material.title
        material.delete()
        messages.success(request, f'Past paper "{paper_title}" deleted successfully.')
    except Material.DoesNotExist:
        messages.error(request, 'Past paper not found or you do not have permission to delete it.')
    
    return redirect('teacher_pastpaper')


@login_required
def delete_assignment(request, assignment_id):
    """Delete an assignment created by the teacher."""
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')
    
    try:
        assignment = Assignment.objects.get(id=assignment_id, created_by=request.user)
        assignment_title = assignment.title
        assignment.delete()
        messages.success(request, f'Assignment "{assignment_title}" deleted successfully.')
    except Assignment.DoesNotExist:
        messages.error(request, 'Assignment not found or you do not have permission to delete it.')
    
    return redirect('teacher_assignment')


@login_required
def delete_material(request, material_id):
    """Delete a material/study note uploaded by the teacher."""
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')
    
    try:
        material = Material.objects.get(id=material_id, uploaded_by=request.user)
        # Ensure it's not a past paper
        if material.description == 'past_paper':
            raise Material.DoesNotExist('Cannot delete past paper from this endpoint')
        material_title = material.title
        material.delete()
        messages.success(request, f'Material "{material_title}" deleted successfully.')
    except Material.DoesNotExist:
        messages.error(request, 'Material not found or you do not have permission to delete it.')
    
    return redirect('teacher_materials')


@login_required
def delete_invitation(request, invitation_id):
    """Delete an invitation sent by the teacher."""
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')
    
    try:
        invitation = Invitation.objects.get(id=invitation_id, sender=request.user)
        student_email = invitation.email
        invitation.delete()
        messages.success(request, f'Invitation for {student_email} has been deleted.')
    except Invitation.DoesNotExist:
        messages.error(request, 'Invitation not found or you do not have permission to delete it.')
    
    return redirect('teacher_invite')

def teacher_results(request):
    # Only teachers allowed
    if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')

    # Get all assignments created by this teacher
    assignments = Assignment.objects.filter(created_by=request.user).order_by('-created_at')
    assignment_contexts = []
    for a in assignments:
        # All enrolled students for this assignment's course
        students = CustomUser.objects.filter(enrollments__course=a.course, role='student').distinct()
        # Existing submissions for this assignment
        subs = {sub.student_id: sub for sub in Submission.objects.filter(assignment=a)}
        assignment_contexts.append({
            'assignment': a,
            'students': list(students),
            'submissions': subs,
        })

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'submit_to_hod':
            course_id = request.POST.get('course_id')
            title = request.POST.get('title', '').strip()
            marksheet_file = request.FILES.get('marksheet_file')
            assignment_id_val = request.POST.get('assignment_id')
            course_obj = Course.objects.filter(id=course_id).first() if course_id else None
            assignment_obj = Assignment.objects.filter(id=assignment_id_val).first() if assignment_id_val else None

            if not course_obj or not title:
                messages.error(request, 'Please provide course and marksheet title.')
                return redirect('teacher_results')

            total_std = 0
            avg_score = 0.0
            if assignment_obj:
                graded_subs = Submission.objects.filter(assignment=assignment_obj, graded=True, marks__isnull=False)
                total_std = graded_subs.count()
                m_list = [s.marks for s in graded_subs]
                avg_score = round(sum(m_list) / len(m_list), 1) if m_list else 0.0
            else:
                total_std = Enrollment.objects.filter(course=course_obj).count()

            MarksheetSubmission.objects.create(
                teacher=request.user,
                course=course_obj,
                assignment=assignment_obj,
                title=title,
                file=marksheet_file,
                total_students=total_std,
                average_score=avg_score,
                status='submitted'
            )
            messages.success(request, f"Marksheet '{title}' submitted to HOD for official review and approval.")
            return redirect('teacher_results')

        assignment_id = request.POST.get('assignment_id')
        if assignment_id:
            try:
                assignment = Assignment.objects.get(id=assignment_id, created_by=request.user)
                selected_context = next((ctx for ctx in assignment_contexts if ctx['assignment'].id == int(assignment_id)), None)
                students = selected_context['students'] if selected_context else CustomUser.objects.filter(enrollments__course=assignment.course, role='student').distinct()
                for stu in students:
                    marks_val = request.POST.get(f'marks_{assignment.id}_{stu.id}', request.POST.get(f'marks_{stu.id}'))
                    grade_val = request.POST.get(f'grade_{assignment.id}_{stu.id}', request.POST.get(f'grade_{stu.id}', ''))
                    feedback_val = request.POST.get(f'feedback_{assignment.id}_{stu.id}', request.POST.get(f'feedback_{stu.id}', ''))
                    sub = Submission.objects.filter(assignment=assignment, student=stu).first()
                    if not sub:
                        sub = Submission.objects.create(assignment=assignment, student=stu)
                    if marks_val is not None and marks_val != '':
                        try:
                            sub.marks = float(marks_val)
                        except ValueError:
                            sub.marks = None
                    sub.grade = grade_val
                    sub.feedback = feedback_val
                    sub.graded = True
                    sub.save()
                if 'publish' in request.POST:
                    assignment.published = True
                    assignment.save()
                    messages.success(request, 'Results published successfully!')
                else:
                    messages.success(request, 'Marks saved (not published).')
                return redirect('teacher_results')
            except Assignment.DoesNotExist:
                messages.error(request, 'Assignment not found.')

    assignments = Assignment.objects.filter(created_by=request.user)
    graded_assignments = [a for a in assignments if Submission.objects.filter(assignment=a, graded=True).exists()]
    assessments_graded = len(graded_assignments)

    all_subs = Submission.objects.filter(assignment__created_by=request.user, graded=True, marks__isnull=False)
    marks_list = [sub.marks for sub in all_subs]
    class_average = int(sum(marks_list) / len(marks_list)) if marks_list else 0

    pending_grading = Submission.objects.filter(assignment__created_by=request.user, graded=False).count()

    latest_published_results = []
    for a in assignments.filter(published=True).order_by('-created_at')[:5]:
        subs = Submission.objects.filter(assignment=a, graded=True, marks__isnull=False)
        sub_count = subs.count()
        marks = [s.marks for s in subs]
        avg = int(sum(marks) / len(marks)) if marks else 0
        latest_published_results.append({
            'assignment': a,
            'avg_score': avg,
            'student_count': sub_count
        })

    submitted_marksheets = MarksheetSubmission.objects.filter(teacher=request.user).select_related('course', 'assignment').order_by('-submitted_at')
    assigned_c = request.user.assigned_courses.all()
    teacher_courses = assigned_c if assigned_c.exists() else Course.objects.all()

    return render(request, 'MyApp/teacher-results.html', {
        'assignment_contexts': assignment_contexts,
        'assessments_graded': assessments_graded,
        'class_average': class_average,
        'pending_grading': pending_grading,
        'latest_published_results': latest_published_results,
        'submitted_marksheets': submitted_marksheets,
        'teacher_courses': teacher_courses,
    })

def teacher_sessions(request):
    # Former session/analytics views removed from UI; leave placeholder for compatibility.
    messages.error(request, 'This feature has been removed.')
    return redirect('teacher_actions')

@csrf_exempt
def ai_chatbot_api(request):
    """
    BGNU AI Study Tutor and Autonomous Academic Co-Pilot API endpoint.
    Handles general chat as well as autonomous executive tool calling for HOD and Teachers.
    Supports file uploads from mobile/PC picker and PC local storage path.
    """
    import json
    import re
    from django.conf import settings
    from django.http import JsonResponse
    from .academic_agent import run_academic_agent

    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    user_message = ''
    conversation_history = []
    local_path = ''
    uploaded_file = request.FILES.get('file')

    # Parse POST / FormData or JSON Body
    sender_role = ''
    current_path = ''
    if request.POST:
        user_message = request.POST.get('message', '').strip()
        local_path = request.POST.get('local_path', '').strip()
        sender_role = request.POST.get('sender_role', '').strip()
        current_path = request.POST.get('current_path', '').strip()
        history_raw = request.POST.get('history')
        if history_raw:
            try:
                conversation_history = json.loads(history_raw)
            except Exception:
                pass
    elif request.body:
        try:
            body_data = json.loads(request.body.decode('utf-8'))
            user_message = body_data.get('message', '').strip()
            conversation_history = body_data.get('history', [])
            local_path = body_data.get('local_path', '').strip()
            sender_role = body_data.get('sender_role', '').strip()
            current_path = body_data.get('current_path', '').strip()
        except Exception:
            pass

    if not user_message and not uploaded_file and not local_path:
        return JsonResponse({'reply': 'Please enter a message or attach a file.', 'source': 'empty'})

    acting_user = request.user
    if not getattr(acting_user, 'is_authenticated', False) or not getattr(acting_user, 'role', None):
        referer = request.META.get('HTTP_REFERER', '')
        if sender_role == 'hod' or '/hod' in current_path or '/hod' in referer:
            acting_user = CustomUser.objects.filter(role='hod').first() or acting_user
        elif sender_role == 'teacher' or '/teacher' in current_path or '/teacher' in referer:
            acting_user = CustomUser.objects.filter(role='teacher').first() or acting_user

    # If message contains a local Windows path or filename in Downloads/Desktop
    if not local_path and user_message:
        path_match = re.search(r'([a-zA-Z]:\\[^\s\r\n]+\.[a-zA-Z0-9]+)', user_message)
        if path_match:
            local_path = path_match.group(1)
        else:
            m_file = re.search(r'([a-zA-Z0-9_\-]+\.(?:png|jpg|jpeg|pdf|docx?|xlsx?|pptx?|txt|csv|zip))', user_message, re.I)
            if m_file:
                target_fname = m_file.group(1)
                m_fld = re.search(r'\b(download[s]?|desktop|document[s]?|picture[s]?|media)\b', user_message, re.I)
                fld_hint = m_fld.group(1) if m_fld else ''
                from .academic_agent import find_system_file
                found = find_system_file(target_fname, fld_hint)
                if found:
                    local_path = found

    result = run_academic_agent(
        user=acting_user,
        message=user_message,
        uploaded_file=uploaded_file,
        local_path=local_path,
        history=conversation_history
    )

    return JsonResponse(result)


def export_results_csv(request):
    """
    Exports student and faculty assessment records as an Excel-compatible CSV spreadsheet.
    """
    import csv
    from django.http import HttpResponse
    from django.shortcuts import redirect

    if not request.user.is_authenticated:
        return redirect('login')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="BGNU_Assessment_Results.csv"'

    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Student Name', 'Course Name', 'Assessment Title', 'Kind', 'Marks', 'Grade', 'Submission Date'])

    if getattr(request.user, 'role', '') == 'teacher':
        subs = Submission.objects.filter(assignment__created_by=request.user, graded=True).select_related('student', 'assignment', 'assignment__course')
    else:
        subs = Submission.objects.filter(student=request.user, graded=True).select_related('student', 'assignment', 'assignment__course')

    for s in subs:
        writer.writerow([
            s.student.username,
            s.student.get_full_name() or s.student.username,
            s.assignment.course.name if s.assignment and s.assignment.course else 'General',
            s.assignment.title if s.assignment else 'Untitled',
            s.assignment.get_kind_display() if s.assignment else 'Assignment',
            s.marks if s.marks is not None else 'N/A',
            s.grade or 'N/A',
            s.submitted_at.strftime('%Y-%m-%d %H:%M') if s.submitted_at else 'N/A'
        ])

    return response


# ==============================================================================
# HOD (HEAD OF DEPARTMENT) AND TEACHER ATTENDANCE VIEWS
# ==============================================================================

def hod_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if getattr(request.user, 'role', '') != 'hod':
            messages.error(request, 'Access denied: Head of Department (HOD) area only.')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@hod_required
def hod_dashboard(request):
    total_faculty = CustomUser.objects.filter(role='teacher').count()
    total_courses = Course.objects.count()
    total_students = CustomUser.objects.filter(role='student').count()
    pending_marksheets = MarksheetSubmission.objects.filter(status='submitted').count()
    active_tasks = TeacherTask.objects.exclude(status='completed').count()
    today = timezone.now().date()
    today_attendance_count = TeacherAttendance.objects.filter(date=today, status='present').count()

    recent_marksheets = MarksheetSubmission.objects.select_related('teacher', 'course').order_by('-submitted_at')[:6]
    recent_attendance = TeacherAttendance.objects.select_related('teacher', 'course').order_by('-date', '-created_at')[:6]
    recent_tasks = TeacherTask.objects.select_related('teacher', 'course').order_by('-created_at')[:6]
    courses = Course.objects.select_related('teacher').all()[:8]

    return render(request, 'MyApp/hod_dashboard.html', {
        'total_faculty': total_faculty,
        'total_courses': total_courses,
        'total_students': total_students,
        'pending_marksheets': pending_marksheets,
        'active_tasks': active_tasks,
        'today_attendance_count': today_attendance_count,
        'recent_marksheets': recent_marksheets,
        'recent_attendance': recent_attendance,
        'recent_tasks': recent_tasks,
        'courses': courses,
    })

@hod_required
def hod_courses(request):
    teachers = CustomUser.objects.filter(role='teacher').order_by('first_name', 'username')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign':
            course_id = request.POST.get('course_id')
            teacher_id = request.POST.get('teacher_id')
            course = Course.objects.filter(id=course_id).first()
            if course:
                if teacher_id:
                    t = CustomUser.objects.filter(id=teacher_id, role='teacher').first()
                    course.teacher = t
                    t_name = t.get_full_name() or t.username if t else 'Teacher'
                    messages.success(request, f"Course '{course.name}' successfully assigned to {t_name}.")
                else:
                    course.teacher = None
                    messages.success(request, f"Course '{course.name}' is now unassigned.")
                course.save()
        elif action == 'create':
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip()
            teacher_id = request.POST.get('teacher_id')
            if name:
                teacher = CustomUser.objects.filter(id=teacher_id, role='teacher').first() if teacher_id else None
                c, created = Course.objects.get_or_create(name=name, defaults={'code': code, 'teacher': teacher})
                if not created:
                    c.code = code
                    c.teacher = teacher
                    c.save()
                    messages.info(request, f"Course '{c.name}' updated successfully.")
                else:
                    messages.success(request, f"Course '{c.name}' created and assigned successfully.")
        elif action == 'edit_course':
            course_id = request.POST.get('course_id')
            course = Course.objects.filter(id=course_id).first()
            if course:
                name = request.POST.get('name', '').strip()
                code = request.POST.get('code', '').strip()
                teacher_id = request.POST.get('teacher_id')
                if name:
                    course.name = name
                course.code = code
                if teacher_id:
                    course.teacher = CustomUser.objects.filter(id=teacher_id, role='teacher').first()
                else:
                    course.teacher = None
                course.save()
                messages.success(request, f"Course '{course.name}' updated successfully.")
        elif action == 'delete_course':
            course_id = request.POST.get('course_id')
            course = Course.objects.filter(id=course_id).first()
            if course:
                c_name = course.name
                course.delete()
                messages.success(request, f"Course '{c_name}' deleted successfully.")
        return redirect('hod_courses')

    courses = Course.objects.select_related('teacher').all().order_by('name')
    for c in courses:
        c.student_count = c.enrollments.count()
        c.materials_count = c.materials.count()
        c.assignments_count = c.assignments.count()

    return render(request, 'MyApp/hod_courses.html', {
        'courses': courses,
        'teachers': teachers,
    })

@hod_required
def hod_tasks(request):
    teachers = CustomUser.objects.filter(role='teacher').order_by('first_name', 'username')
    courses = Course.objects.all().order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_task':
            teacher_id = request.POST.get('teacher_id')
            course_id = request.POST.get('course_id')
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            due_date = request.POST.get('due_date') or None
            priority = request.POST.get('priority', 'normal')

            teacher = CustomUser.objects.filter(id=teacher_id, role='teacher').first()
            course = Course.objects.filter(id=course_id).first() if course_id else None

            if teacher and title:
                TeacherTask.objects.create(
                    hod=request.user,
                    teacher=teacher,
                    course=course,
                    title=title,
                    description=description,
                    due_date=due_date,
                    priority=priority,
                    status='pending'
                )
                messages.success(request, f"Task '{title}' successfully assigned to {teacher.get_full_name() or teacher.username}.")
        elif action == 'update_status':
            task_id = request.POST.get('task_id')
            status = request.POST.get('status')
            task = TeacherTask.objects.filter(id=task_id).first()
            if task and status in ['pending', 'in_progress', 'completed']:
                task.status = status
                task.save()
                messages.success(request, f"Task '{task.title}' status updated to {task.get_status_display()}.")
        elif action == 'edit_task':
            task_id = request.POST.get('task_id')
            task = TeacherTask.objects.filter(id=task_id).first()
            if task:
                title = request.POST.get('title', '').strip()
                description = request.POST.get('description', '').strip()
                due_date = request.POST.get('due_date') or None
                priority = request.POST.get('priority', 'normal')
                teacher_id = request.POST.get('teacher_id')
                course_id = request.POST.get('course_id')

                if title:
                    task.title = title
                task.description = description
                task.due_date = due_date
                task.priority = priority
                if teacher_id:
                    task.teacher = CustomUser.objects.filter(id=teacher_id, role='teacher').first()
                if course_id:
                    task.course = Course.objects.filter(id=course_id).first()
                elif course_id == '':
                    task.course = None
                task.save()
                messages.success(request, f"Task '{task.title}' updated successfully.")
        elif action == 'delete_task':
            task_id = request.POST.get('task_id')
            TeacherTask.objects.filter(id=task_id).delete()
            messages.success(request, "Task deleted successfully.")
        return redirect('hod_tasks')

    tasks = TeacherTask.objects.select_related('teacher', 'course', 'hod').order_by('-created_at')
    return render(request, 'MyApp/hod_tasks.html', {
        'tasks': tasks,
        'teachers': teachers,
        'courses': courses,
    })

@hod_required
def hod_attendance(request):
    teachers = CustomUser.objects.filter(role='teacher').order_by('first_name', 'username')
    courses = Course.objects.all().order_by('name')

    records = TeacherAttendance.objects.select_related('teacher', 'course').order_by('-date', '-created_at')

    teacher_id = request.GET.get('teacher_id')
    if teacher_id:
        records = records.filter(teacher_id=teacher_id)

    date_filter = request.GET.get('date')
    if date_filter:
        records = records.filter(date=date_filter)

    total_conducted = TeacherAttendance.objects.filter(status='present').count()
    total_absent = TeacherAttendance.objects.filter(status='absent').count()
    total_leave = TeacherAttendance.objects.filter(status='leave').count()

    return render(request, 'MyApp/hod_attendance.html', {
        'records': records,
        'teachers': teachers,
        'courses': courses,
        'total_conducted': total_conducted,
        'total_absent': total_absent,
        'total_leave': total_leave,
        'selected_teacher': teacher_id,
        'selected_date': date_filter,
    })

@hod_required
def hod_marksheets(request):
    if request.method == 'POST':
        marksheet_id = request.POST.get('marksheet_id')
        status = request.POST.get('status')
        feedback = request.POST.get('hod_feedback', '').strip()
        ms = MarksheetSubmission.objects.filter(id=marksheet_id).first()
        if ms and status in ['approved', 'revision_requested', 'submitted']:
            ms.status = status
            ms.hod_feedback = feedback
            ms.reviewed_at = timezone.now()
            ms.save()
            messages.success(request, f"Marksheet '{ms.title}' status updated to {ms.get_status_display()}.")
        return redirect('hod_marksheets')

    marksheets = MarksheetSubmission.objects.select_related('teacher', 'course', 'assignment').order_by('-submitted_at')
    pending_count = marksheets.filter(status='submitted').count()
    approved_count = marksheets.filter(status='approved').count()
    revision_count = marksheets.filter(status='revision_requested').count()

    return render(request, 'MyApp/hod_marksheets.html', {
        'marksheets': marksheets,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'revision_count': revision_count,
    })

@hod_required
def hod_student_roster(request):
    import csv
    from django.http import HttpResponse

    course_id = request.GET.get('course_id')
    course = Course.objects.filter(id=course_id).first() if course_id else None

    response = HttpResponse(content_type='text/csv')
    filename = f"BGNU_Student_Roster_{course.code if course and course.code else 'Department'}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Student_ID', 'Password', 'Full_Name', 'Email', 'Phone_Number', 'Course_Name'])

    if course:
        enrollments = Enrollment.objects.filter(course=course).select_related('student')
        for en in enrollments:
            s = en.student
            writer.writerow([
                s.username,
                'bgnu1234',
                s.get_full_name() or s.username,
                s.email or f"{s.username}@bgnu.edu.pk",
                s.phone_number or '03001234567',
                course.name
            ])
    else:
        # Provide sample template rows so HOD can distribute to teachers
        writer.writerow(['s202601', 'bgnu1234', 'Muhammad Ali', 'm.ali@bgnu.edu.pk', '03001112233', 'CS101 - Intro to AI'])
        writer.writerow(['s202602', 'bgnu1234', 'Fatima Noor', 'f.noor@bgnu.edu.pk', '03002223344', 'CS101 - Intro to AI'])
        writer.writerow(['s202603', 'bgnu1234', 'Hamza Tariq', 'h.tariq@bgnu.edu.pk', '03003334455', 'CS102 - Data Structures'])
        writer.writerow(['s202604', 'bgnu1234', 'Ayesha Malik', 'a.malik@bgnu.edu.pk', '03004445566', 'CS102 - Data Structures'])

    return response

@hod_required
def hod_manage_users(request):
    courses = Course.objects.all().order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_hod':
            # "Aik HOD differnet HOD bhi add kr sktha hai."
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '').strip()
            full_name = request.POST.get('full_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone_number', '').strip()

            if not username or not password:
                messages.error(request, 'Username and password are required.')
            elif CustomUser.objects.filter(username=username).exists():
                messages.error(request, f"User ID / Username '{username}' already exists.")
            else:
                new_hod = CustomUser.objects.create_user(
                    username=username,
                    password=password,
                    role='hod',
                    email=email,
                    phone_number=phone
                )
                if full_name:
                    parts = full_name.split(None, 1)
                    new_hod.first_name = parts[0]
                    new_hod.last_name = parts[1] if len(parts) > 1 else ''
                    new_hod.save()
                messages.success(request, f"New HOD account for '{full_name or username}' created successfully.")

        elif action == 'create_teacher':
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '').strip()
            full_name = request.POST.get('full_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone_number', '').strip()
            course_id = request.POST.get('course_id')

            if not username or not password:
                messages.error(request, 'Username and password are required.')
            elif CustomUser.objects.filter(username=username).exists():
                messages.error(request, f"User ID / Username '{username}' already exists.")
            else:
                new_teacher = CustomUser.objects.create_user(
                    username=username,
                    password=password,
                    role='teacher',
                    email=email,
                    phone_number=phone
                )
                if full_name:
                    parts = full_name.split(None, 1)
                    new_teacher.first_name = parts[0]
                    new_teacher.last_name = parts[1] if len(parts) > 1 else ''
                    new_teacher.save()

                if course_id:
                    course = Course.objects.filter(id=course_id).first()
                    if course:
                        course.teacher = new_teacher
                        course.save()

                messages.success(request, f"Faculty member '{full_name or username}' registered successfully.")

        elif action == 'edit_user':
            user_id = request.POST.get('user_id')
            target_user = CustomUser.objects.filter(id=user_id).first()
            if not target_user:
                messages.error(request, 'User not found.')
                return redirect('hod_manage_users')

            new_username = request.POST.get('username', '').strip()
            new_password = request.POST.get('password', '').strip()
            full_name = request.POST.get('full_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone_number', '').strip()
            course_id = request.POST.get('course_id')

            if new_username and new_username != target_user.username:
                if CustomUser.objects.filter(username=new_username).exclude(id=target_user.id).exists():
                    messages.error(request, f"Username '{new_username}' is already taken.")
                    return redirect('hod_manage_users')
                target_user.username = new_username

            if new_password:
                target_user.set_password(new_password)

            if full_name:
                parts = full_name.split(None, 1)
                target_user.first_name = parts[0]
                target_user.last_name = parts[1] if len(parts) > 1 else ''

            if email is not None:
                target_user.email = email
            if phone is not None:
                target_user.phone_number = phone

            target_user.save()

            if target_user.role == 'teacher' and course_id is not None:
                if course_id:
                    c = Course.objects.filter(id=course_id).first()
                    if c:
                        c.teacher = target_user
                        c.save()
                else:
                    Course.objects.filter(teacher=target_user).update(teacher=None)

            messages.success(request, f"User account '{target_user.username}' successfully updated.")

        elif action == 'delete_user':
            user_id = request.POST.get('user_id')
            target_user = CustomUser.objects.filter(id=user_id).first()
            if not target_user:
                messages.error(request, 'User not found.')
                return redirect('hod_manage_users')

            if target_user.id == request.user.id:
                messages.error(request, 'You cannot delete your own active HOD account.')
                return redirect('hod_manage_users')

            u_name = target_user.get_full_name() or target_user.username
            target_user.delete()
            messages.success(request, f"User '{u_name}' has been permanently removed.")

        return redirect('hod_manage_users')

    hods = CustomUser.objects.filter(role='hod').order_by('username')
    teachers = CustomUser.objects.filter(role='teacher').prefetch_related('assigned_courses').order_by('first_name', 'username')

    return render(request, 'MyApp/hod_users.html', {
        'hods': hods,
        'teachers': teachers,
        'courses': courses,
    })

@login_required
def teacher_attendance(request):
    if not hasattr(request.user, 'role') or request.user.role != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('login')

    assigned_courses = request.user.assigned_courses.all()
    courses = assigned_courses if assigned_courses.exists() else Course.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'log_lecture':
            course_id = request.POST.get('course_id')
            date_val = request.POST.get('date') or timezone.now().date()
            status = request.POST.get('status', 'present')
            topic = request.POST.get('topic_covered', '').strip()
            students_present = request.POST.get('students_present', 0)
            remarks = request.POST.get('remarks', '').strip()

            course = Course.objects.filter(id=course_id).first()
            if not course:
                messages.error(request, 'Please select a valid course.')
            else:
                try:
                    s_present = int(students_present)
                except ValueError:
                    s_present = 0

                TeacherAttendance.objects.create(
                    teacher=request.user,
                    course=course,
                    date=date_val,
                    status=status,
                    topic_covered=topic,
                    students_present=s_present,
                    remarks=remarks
                )
                messages.success(request, f"Lecture log for '{course.name}' on {date_val} submitted to HOD.")
        elif action == 'update_task':
            task_id = request.POST.get('task_id')
            new_status = request.POST.get('status')
            task = TeacherTask.objects.filter(id=task_id, teacher=request.user).first()
            if task and new_status in ['pending', 'in_progress', 'completed']:
                task.status = new_status
                task.save()
                messages.success(request, f"Task '{task.title}' updated to {task.get_status_display()}.")

        return redirect('teacher_attendance')

    my_logs = TeacherAttendance.objects.filter(teacher=request.user).select_related('course').order_by('-date', '-created_at')[:20]
    my_tasks = TeacherTask.objects.filter(teacher=request.user).select_related('course', 'hod').order_by('-created_at')

    return render(request, 'MyApp/teacher_attendance.html', {
        'courses': courses,
        'my_logs': my_logs,
        'my_tasks': my_tasks,
    })


@hod_required
def hod_notifications(request):
    """
    HOD Official Announcements and Circulars Control Hub.
    Allows HOD to dispatch targeted notifications to:
    1. Specific faculty member (individual_teacher)
    2. All faculty members (all_teachers)
    3. All enrolled students (all_students)
    4. Relevant teacher and students of a specific course (course_relevant)
    5. Campus-wide / everyone (everyone)
    """
    teachers = CustomUser.objects.filter(role='teacher').order_by('first_name', 'last_name', 'username')
    courses = Course.objects.all().select_related('teacher').order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete_notification':
            notif_id = request.POST.get('notification_id')
            Notification.objects.filter(id=notif_id, sender=request.user).delete()
            messages.success(request, 'Notification removed from dispatch history.')
            return redirect('hod_notifications')

        title = request.POST.get('title', '').strip()
        message = request.POST.get('message', '').strip()
        priority = request.POST.get('priority', 'normal')
        audience_type = request.POST.get('audience_type', 'individual_teacher')

        if not title or not message:
            messages.error(request, 'Please provide both announcement title and message content.')
            return redirect('hod_notifications')

        if priority not in ['normal', 'urgent', 'exam', 'meeting']:
            priority = 'normal'

        if audience_type == 'individual_teacher':
            teacher_id = request.POST.get('teacher_id')
            teacher = CustomUser.objects.filter(id=teacher_id, role='teacher').first()
            if not teacher:
                messages.error(request, 'Please select a valid faculty member.')
                return redirect('hod_notifications')
            Notification.objects.create(
                sender=request.user,
                recipient=teacher,
                title=title,
                message=message,
                priority=priority,
                audience_type='individual_teacher'
            )
            t_name = teacher.get_full_name() or teacher.username
            messages.success(request, f"Official notice dispatched to {t_name}.")

        elif audience_type == 'all_teachers':
            all_teachers = list(CustomUser.objects.filter(role='teacher'))
            if not all_teachers:
                messages.warning(request, 'No faculty members found in department.')
                return redirect('hod_notifications')
            to_create = [
                Notification(
                    sender=request.user,
                    recipient=t,
                    title=title,
                    message=message,
                    priority=priority,
                    audience_type='all_teachers'
                ) for t in all_teachers
            ]
            Notification.objects.bulk_create(to_create)
            messages.success(request, f"Circular broadcasted to all {len(to_create)} faculty members.")

        elif audience_type == 'all_students':
            all_students = list(CustomUser.objects.filter(role='student'))
            if not all_students:
                messages.warning(request, 'No students registered in the system.')
                return redirect('hod_notifications')
            to_create = [
                Notification(
                    sender=request.user,
                    recipient=s,
                    title=title,
                    message=message,
                    priority=priority,
                    audience_type='all_students'
                ) for s in all_students
            ]
            Notification.objects.bulk_create(to_create)
            messages.success(request, f"Announcement broadcasted to all {len(to_create)} students.")

        elif audience_type == 'course_relevant':
            course_id = request.POST.get('course_id')
            course = Course.objects.filter(id=course_id).first()
            if not course:
                messages.error(request, 'Please select a valid course for this notice.')
                return redirect('hod_notifications')

            recipients_dict = {}
            if course.teacher:
                recipients_dict[course.teacher.id] = course.teacher

            enrolled_students = CustomUser.objects.filter(enrollments__course=course).distinct()
            for s in enrolled_students:
                recipients_dict[s.id] = s

            if not recipients_dict:
                messages.warning(request, f"No instructor or students currently enrolled in '{course.name}'.")
                return redirect('hod_notifications')

            to_create = [
                Notification(
                    sender=request.user,
                    recipient=u,
                    course=course,
                    title=title,
                    message=message,
                    priority=priority,
                    audience_type='course_relevant'
                ) for u in recipients_dict.values()
            ]
            Notification.objects.bulk_create(to_create)
            teacher_note = f" (including instructor {course.teacher.username})" if course.teacher else ""
            messages.success(request, f"Notification delivered to {len(to_create)} members of '{course.name}'{teacher_note}.")

        elif audience_type == 'everyone':
            all_users = list(CustomUser.objects.filter(role__in=['teacher', 'student']))
            to_create = [
                Notification(
                    sender=request.user,
                    recipient=u,
                    title=title,
                    message=message,
                    priority=priority,
                    audience_type='everyone'
                ) for u in all_users
            ]
            Notification.objects.bulk_create(to_create)
            messages.success(request, f"Campus-wide broadcast dispatched to {len(to_create)} users.")

        else:
            messages.error(request, 'Invalid audience selected.')

        return redirect('hod_notifications')

    sent_notifications = Notification.objects.filter(sender=request.user).select_related('recipient', 'course').order_by('-created_at')[:40]

    stats = {
        'total_sent': Notification.objects.filter(sender=request.user).count(),
        'total_faculty': teachers.count(),
        'total_students': CustomUser.objects.filter(role='student').count(),
        'total_courses': courses.count(),
        'urgent_count': Notification.objects.filter(sender=request.user, priority='urgent').count(),
    }

    return render(request, 'MyApp/hod_notifications.html', {
        'teachers': teachers,
        'courses': courses,
        'sent_notifications': sent_notifications,
        'stats': stats,
    })


@login_required
def notifications_list(request):
    """
    Unified Notification Inbox for logged-in user (Student, Teacher, or HOD).
    """
    filter_type = request.GET.get('filter', 'all')
    qs = Notification.objects.filter(recipient=request.user).select_related('sender', 'course').order_by('-created_at')

    if filter_type == 'unread':
        qs = qs.filter(is_read=False)
    elif filter_type == 'urgent':
        qs = qs.filter(priority='urgent')
    elif filter_type == 'course':
        qs = qs.filter(course__isnull=False)

    total_count = Notification.objects.filter(recipient=request.user).count()
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    urgent_count = Notification.objects.filter(recipient=request.user, priority='urgent').count()

    return render(request, 'MyApp/notifications_list.html', {
        'notifications': qs,
        'filter_type': filter_type,
        'total_count': total_count,
        'unread_count': unread_count,
        'urgent_count': urgent_count,
    })


@login_required
def mark_notification_read(request, notification_id):
    """
    Mark a single notification as read.
    """
    notif = Notification.objects.filter(id=notification_id, recipient=request.user).first()
    if notif:
        notif.is_read = True
        notif.read_at = timezone.now()
        notif.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        remaining = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return JsonResponse({'status': 'ok', 'unread_count': remaining})

    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'notifications_list'
    return redirect(next_url)


@login_required
def mark_all_notifications_read(request):
    """
    Mark all notifications for the current user as read.
    """
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'status': 'ok', 'unread_count': 0})

    messages.success(request, 'All notifications marked as read.')
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'notifications_list'
    return redirect(next_url)
