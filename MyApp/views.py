# pyrefly: ignore [missing-import]
from django.shortcuts import render, redirect
# pyrefly: ignore [missing-import]
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
# pyrefly: ignore [missing-import]
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie, get_token
import re
from django.db import models
from django.utils import timezone
from .models import Submission, Message, Course, Assignment, Material, Enrollment, CustomUser, QuizQuestion


def parse_fill_in_blanks(text):
    blanks = re.findall(r'\[\[(.+?)\]\]', text)
    if blanks:
        return blanks
    underscores = re.findall(r'_{2,}', text)
    return [f'Blank {i + 1}' for i, _ in enumerate(underscores)] if underscores else []


def index(request):
    return render(request, 'MyApp/index.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('student_id')
        password = request.POST.get('password')
        role = request.POST.get('role')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # If role is provided, verify it matches the user's role
            if role:
                if getattr(user, 'role', None) == role:
                    auth_login(request, user)
                    if role == 'student':
                        return redirect('student_dashboard')
                    elif role == 'teacher':
                        return redirect('teacher_dashboard')
                else:
                    messages.error(request, f"Access Denied: You are not registered as a {role.capitalize()}.")
            else:
                # No role supplied; log in user and redirect based on stored role
                auth_login(request, user)
                if getattr(user, 'role', '') == 'teacher':
                    return redirect('teacher_dashboard')
                else:
                    return redirect('student_dashboard')
        else:
            messages.error(request, "Invalid User ID or Password")
            
    return render(request, 'MyApp/login.html')

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
    
    display_name = request.user.get_full_name() or request.user.username
    
    # Get courses where this teacher has created assignments or materials
    teacher_courses = Course.objects.filter(
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

    teacher_courses = Course.objects.filter(
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

        course_obj, _ = Course.objects.get_or_create(name=course_name)

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

    courses = Course.objects.all()
    students = CustomUser.objects.filter(role='student', enrollments__isnull=False).distinct().prefetch_related('enrollments__course').order_by('first_name', 'last_name', 'username')
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

    if request.method == 'POST':
        sub, created = Submission.objects.get_or_create(assignment=assignment, student=request.user)
        if assignment.kind == 'quiz' and assignment.quiz_questions.exists():
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
            sub.answer_text = ''
        else:
            uploaded = request.FILES.get('file')
            answer_text = request.POST.get('answer_text', '')
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
            os.unlink(tmp_path)
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
    
    # Check if submission has either file or text
    if not submission.file and not submission.answer_text:
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
        
        else:
            # Analyze text submission
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp:
                tmp.write(submission.answer_text)
                tmp_path = tmp.name
            
            try:
                result = predict(tmp_path)
            finally:
                try:
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

        # Save file directly without compression
        original_size = uploaded_file.size

        # Get or create the course
        course_obj, _ = Course.objects.get_or_create(name=course_name)
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
    courses = Course.objects.all()
    total_files = materials.count()
    total_bytes = sum(m.file.size for m in materials if m.file)
    if total_bytes < 1024:
        storage_used = f"{total_bytes} B"
    elif total_bytes < 1024 * 1024:
        storage_used = f"{total_bytes / 1024:.1f} KB"
    elif total_bytes < 1024 * 1024 * 1024:
        storage_used = f"{total_bytes / (1024 * 1024):.1f} MB"
    else:
        storage_used = f"{total_bytes / (1024 * 1024 * 1024):.1f} GB"

    teacher_courses = Course.objects.filter(
        models.Q(assignments__created_by=request.user) |
        models.Q(materials__uploaded_by=request.user)
    ).distinct()
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
    # Manual student invite: teacher supplies roll(s) and password(s) and assigns to a course.
    # Only allow users with role 'teacher' to access this view.
    if not hasattr(request.user, 'role') or request.user.role != 'teacher':
        messages.error(request, 'Access denied: teacher only area.')
        return redirect('teacher_actions')
    if request.method == 'POST':
        # Teachers provide a single course name and optional course code (id).
        course_name = request.POST.get('course_name') or request.POST.get('course')
        course_code = request.POST.get('course_code') or request.POST.get('course_id')
        students_text = request.POST.get('students')  # multiple lines: roll,password[,Full Name]
        single_roll = request.POST.get('student_roll')
        single_pass = request.POST.get('student_password')
        single_name = request.POST.get('student_name')

        if not course_name:
            messages.error(request, 'Please provide a course name.')
            return redirect('teacher_invite')

        entries = []
        if students_text:
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
                entries.append((roll, pwd, name))
        elif single_roll and single_pass:
            entries.append((single_roll.strip(), single_pass.strip(), single_name.strip() if single_name else ''))
        else:
            messages.error(request, 'Please provide at least one student (roll,password).')
            return redirect('teacher_invite')

        created = 0
        enrolled = 0
        course_obj, created_course = Course.objects.get_or_create(name=course_name, defaults={'code': course_code or ''})
        # if course existed but code provided, update code
        if course_obj and course_code and course_obj.code != course_code:
            course_obj.code = course_code
            course_obj.save()

        # remember last course added by this teacher in session for convenience
        try:
            request.session['last_course_id'] = course_obj.id
        except Exception:
            pass

        for roll, pwd, name in entries:
            if not roll or not pwd:
                continue
            try:
                user, was_created = CustomUser.objects.get_or_create(username=roll, defaults={'role': 'student', 'email': ''})
                # Set/update password
                user.set_password(pwd)
                user.role = 'student'
                if name:
                    # Try to split into first/last name
                    parts = name.split(None, 1)
                    user.first_name = parts[0]
                    user.last_name = parts[1] if len(parts) > 1 else ''
                user.save()
                if was_created:
                    created += 1

                # Enroll student in course
                enroll_obj, enroll_created = Enrollment.objects.get_or_create(student=user, course=course_obj)
                if enroll_created:
                    enrolled += 1
            except Exception:
                # continue processing remaining entries
                continue

        messages.success(request, f"Processed students: created {created}, newly enrolled {enrolled}.")
        return redirect('teacher_invite')

    # GET: show form. If the teacher previously created a course, pre-fill it and show recent enrollments for that course.
    last_course = None
    recent_enrollments = []
    course_name_prefill = ''
    course_code_prefill = ''
    last_course_id = request.session.get('last_course_id')
    if last_course_id:
        try:
            last_course = Course.objects.filter(id=last_course_id).first()
            if last_course:
                course_name_prefill = last_course.name
                course_code_prefill = last_course.code or ''
                recent_enrollments = Enrollment.objects.select_related('student', 'course').filter(course=last_course).order_by('-enrolled_at')[:30]
        except Exception:
            last_course = None

    return render(request, 'MyApp/teacher-invite.html', {
        'last_course': last_course,
        'course_name_prefill': course_name_prefill,
        'course_code_prefill': course_code_prefill,
        'recent_enrollments': recent_enrollments,
        'invitations': Invitation.objects.filter(sender=request.user)
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
    # Run detection on the file path
    file_path = material.file.path
    try:
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

        # Save file directly without compression
        original_name = uploaded_file.name
        original_size = uploaded_file.size

        # Get or create the course
        course_obj, created = Course.objects.get_or_create(name=course_name)
        
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

    # GET - Display upload form and list of past papers
    courses = Course.objects.all()
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
        assignment_id = request.POST.get('assignment_id')
        if assignment_id:
            try:
                assignment = Assignment.objects.get(id=assignment_id, created_by=request.user)
                selected_context = next((ctx for ctx in assignment_contexts if ctx['assignment'].id == int(assignment_id)), None)
                students = selected_context['students'] if selected_context else CustomUser.objects.filter(enrollments__course=assignment.course, role='student').distinct()
                for stu in students:
                    marks_val = request.POST.get(f'marks_{stu.id}')
                    grade_val = request.POST.get(f'grade_{stu.id}', '')
                    feedback_val = request.POST.get(f'feedback_{stu.id}', '')
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

    return render(request, 'MyApp/teacher-results.html', {
        'assignment_contexts': assignment_contexts,
        'assessments_graded': assessments_graded,
        'class_average': class_average,
        'pending_grading': pending_grading,
        'latest_published_results': latest_published_results,
    })

def teacher_sessions(request):
    # Former session/analytics views removed from UI; leave placeholder for compatibility.
    messages.error(request, 'This feature has been removed.')
    return redirect('teacher_actions')