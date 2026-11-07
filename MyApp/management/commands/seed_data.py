from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone
from MyApp.models import CustomUser, Course, Enrollment, Assignment, QuizQuestion, Material, Message

class Command(BaseCommand):
    help = 'Populates the database with demo courses, teachers, students, assignments, quizzes, and materials.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding demo data for AI Offline Learning Platform...'))

        # 0. Create or get Demo HOD
        hod, h_created = CustomUser.objects.get_or_create(
            username='hod',
            defaults={
                'role': 'hod',
                'first_name': 'HOD',
                'last_name': 'Administrator',
                'phone_number': '03009876543',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        hod.set_password('hod123')
        hod.save()
        if h_created:
            self.stdout.write(self.style.SUCCESS('Created HOD account: username="hod", password="hod123"'))
        else:
            self.stdout.write('HOD account already exists. Password updated to "hod123".')

        # 1. Create or get Demo Teacher
        teacher, t_created = CustomUser.objects.get_or_create(
            username='teacher',
            defaults={
                'role': 'teacher',
                'first_name': 'Tariq',
                'last_name': 'Mahmood',
                'phone_number': '03001234567',
                'is_staff': True,
            }
        )
        teacher.set_password('teacher123')
        teacher.save()
        if t_created:
            self.stdout.write(self.style.SUCCESS('Created teacher account: username="teacher", password="teacher123"'))
        else:
            self.stdout.write('Teacher account already exists. Password updated to "teacher123".')

        # 2. Create or get Demo Student
        student, s_created = CustomUser.objects.get_or_create(
            username='student',
            defaults={
                'role': 'student',
                'first_name': 'Ali',
                'last_name': 'Raza',
                'phone_number': '03007654321',
            }
        )
        student.set_password('student123')
        student.save()
        if s_created:
            self.stdout.write(self.style.SUCCESS('Created student account: username="student", password="student123"'))
        else:
            self.stdout.write('Student account already exists. Password updated to "student123".')

        # 3. Create Sample Courses
        course_ai, _ = Course.objects.get_or_create(name='CS110 - Artificial Intelligence', defaults={'code': 'CS110'})
        course_ds, _ = Course.objects.get_or_create(name='CS102 - Data Structures & Algorithms', defaults={'code': 'CS102'})
        course_db, _ = Course.objects.get_or_create(name='CS120 - Database Systems', defaults={'code': 'CS120'})

        # 4. Enroll student
        Enrollment.objects.get_or_create(student=student, course=course_ai)
        Enrollment.objects.get_or_create(student=student, course=course_ds)
        Enrollment.objects.get_or_create(student=student, course=course_db)

        # 5. Create Sample Study Materials
        if not Material.objects.filter(title='Lecture 01 - Foundations of Artificial Intelligence').exists():
            mat1 = Material(
                title='Lecture 01 - Foundations of Artificial Intelligence',
                course=course_ai,
                uploaded_by=teacher,
                description='Comprehensive lecture notes covering heuristic search, state spaces, and knowledge representation for offline revision.'
            )
            mat1.file.save(
                'lecture01_ai_foundations.txt',
                ContentFile(b'Lecture 01: Foundations of Artificial Intelligence\n\nTopics covered:\n1. State space search\n2. BFS and DFS algorithms\n3. A* Search and Admissible Heuristics\n4. Knowledge Graphs\n\nOffline study material provided by BGNU Department of CS & IT.')
            )

        # 6. Create Sample Past Paper
        if not Material.objects.filter(title='Midterm Examination 2025 - Artificial Intelligence', description='past_paper').exists():
            pp1 = Material(
                title='Midterm Examination 2025 - Artificial Intelligence',
                course=course_ai,
                uploaded_by=teacher,
                description='past_paper'
            )
            pp1.file.save(
                'midterm_2025_cs110.txt',
                ContentFile(b'Baba Guru Nanak University Nankana Sahib\nDepartment of Computer Science & IT\nMidterm Exam 2025 - CS110 AI\n\nSection A: Multiple Choice Questions\nSection B: Problem Solving (Alpha-Beta Pruning, A* Search)')
            )

        # 7. Create Sample Homework Assignment
        hw, hw_created = Assignment.objects.get_or_create(
            title='Assignment 1: Uninformed vs Heuristic Search',
            course=course_ai,
            defaults={
                'kind': 'homework',
                'description': 'Implement BFS, DFS, and A* Search in Python to solve the 8-puzzle problem. Upload your python source code and an explanation document.',
                'created_by': teacher,
                'published': True,
                'deadline': timezone.now() + timezone.timedelta(days=7),
            }
        )
        if hw_created:
            Message.objects.create(
                sender=teacher,
                recipient=student,
                course=course_ai,
                content=f"New assignment '{hw.title}' has been assigned to your course {course_ai.name}."
            )

        # 8. Create Sample Quiz with Questions
        quiz, q_created = Assignment.objects.get_or_create(
            title='Quiz 1: Intelligent Agents & Search',
            course=course_ai,
            defaults={
                'kind': 'quiz',
                'quiz_type': 'mcq',
                'description': 'Test your understanding of rational agents, heuristics, and graph search.',
                'created_by': teacher,
                'published': True,
                'deadline': timezone.now() + timezone.timedelta(days=3),
            }
        )
        if q_created:
            QuizQuestion.objects.create(
                assignment=quiz,
                question_text='Which search strategy is guaranteed to find the shortest path on unweighted graphs?',
                question_type='mcq',
                options={
                    'A': 'Depth-First Search (DFS)',
                    'B': 'Breadth-First Search (BFS)',
                    'C': 'Depth-Limited Search',
                    'D': 'Random Walk'
                },
                expected_answer='B',
                order=0
            )
            QuizQuestion.objects.create(
                assignment=quiz,
                question_text='An admissible heuristic in A* search never _____ the true cost to reach the goal.',
                question_type='fillblank',
                blanks=['Blank 1'],
                expected_answer='overestimates',
                order=1
            )
            QuizQuestion.objects.create(
                assignment=quiz,
                question_text='Explain the primary difference between a Reflex Agent and a Goal-Based Agent.',
                question_type='manual',
                expected_answer='Reflex agents act solely based on current percepts, whereas goal-based agents consider how their actions will achieve desired goal states.',
                order=2
            )
            Message.objects.create(
                sender=teacher,
                recipient=student,
                course=course_ai,
                content=f"New quiz '{quiz.title}' is now available for {course_ai.name}. Complete it before the due date."
            )

        self.stdout.write(self.style.SUCCESS('\nDemo data successfully seeded!'))
        self.stdout.write(self.style.SUCCESS('Teacher login: username="teacher", password="teacher123"'))
        self.stdout.write(self.style.SUCCESS('Student login: username="student", password="student123"'))

