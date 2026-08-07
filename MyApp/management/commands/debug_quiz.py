from django.core.management.base import BaseCommand
from MyApp.models import Assignment, Course, Enrollment, CustomUser, Message, Submission

class Command(BaseCommand):
    help = 'Debug quiz visibility and messaging issues'

    def add_arguments(self, parser):
        parser.add_argument('--teacher', type=str, help='Teacher username')
        parser.add_argument('--student', type=str, help='Student username')
        parser.add_argument('--course', type=str, help='Course name')
        parser.add_argument('--full', action='store_true', help='Show full details')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== QUIZ DEBUG REPORT ===\n'))
        
        # 1. Check published quizzes
        quizzes = Assignment.objects.filter(published=True, kind='quiz')
        self.stdout.write(f"Total published quizzes: {quizzes.count()}")
        for quiz in quizzes:
            self.stdout.write(f"\n  Quiz: {quiz.title}")
            self.stdout.write(f"    Course: {quiz.course.name}")
            self.stdout.write(f"    Created by: {quiz.created_by.username}")
            self.stdout.write(f"    Published: {quiz.published}")
            self.stdout.write(f"    Assigned to: {quiz.assigned_student.username if quiz.assigned_student else 'All enrolled'}")
            self.stdout.write(f"    Questions: {quiz.quiz_questions.count()}")
        
        # 2. Check enrollments
        self.stdout.write(f"\n\nTotal Enrollments: {Enrollment.objects.count()}")
        for course in Course.objects.all():
            students = Enrollment.objects.filter(course=course).count()
            self.stdout.write(f"  {course.name}: {students} students")
        
        # 3. Check messages
        messages = Message.objects.all()
        self.stdout.write(f"\n\nTotal Messages: {messages.count()}")
        for msg in messages.order_by('-created_at')[:10]:
            self.stdout.write(f"  From {msg.sender.username} to {msg.recipient.username}: {msg.content[:40]}")
        
        # 4. If teacher specified, check their quizzes
        if options['teacher']:
            self.stdout.write(f"\n\nTeacher: {options['teacher']}")
            teacher = CustomUser.objects.filter(username=options['teacher']).first()
            if teacher:
                teacher_quizzes = Assignment.objects.filter(created_by=teacher, kind='quiz')
                self.stdout.write(f"  Quizzes created: {teacher_quizzes.count()}")
                for q in teacher_quizzes:
                    self.stdout.write(f"    - {q.title} (published: {q.published})")
        
        # 5. If student specified, check their enrollments and messages
        if options['student']:
            self.stdout.write(f"\n\nStudent: {options['student']}")
            student = CustomUser.objects.filter(username=options['student']).first()
            if student:
                enrollments = Enrollment.objects.filter(student=student)
                self.stdout.write(f"  Enrolled courses: {enrollments.count()}")
                for e in enrollments:
                    self.stdout.write(f"    - {e.course.name}")
                
                student_messages = Message.objects.filter(recipient=student)
                self.stdout.write(f"  Messages received: {student_messages.count()}")
                for msg in student_messages:
                    self.stdout.write(f"    - From {msg.sender.username}: {msg.content[:40]}")
                
                # Check visible quizzes
                enrolled_courses = Course.objects.filter(enrollments__student=student)
                visible_quizzes = Assignment.objects.filter(
                    published=True,
                    kind='quiz'
                ).filter(
                    course__in=enrolled_courses
                ).exclude(
                    assigned_student__isnull=False
                ).exclude(
                    assigned_student=student
                )
                self.stdout.write(f"  Visible quizzes: {visible_quizzes.count()}")
                for q in visible_quizzes:
                    self.stdout.write(f"    - {q.title} ({q.course.name})")
        
        # 6. If course specified, show details
        if options['course']:
            self.stdout.write(f"\n\nCourse: {options['course']}")
            course = Course.objects.filter(name=options['course']).first()
            if course:
                students = Enrollment.objects.filter(course=course).count()
                self.stdout.write(f"  Enrolled students: {students}")
                quizzes = Assignment.objects.filter(course=course, kind='quiz', published=True).count()
                self.stdout.write(f"  Published quizzes: {quizzes}")
        
        self.stdout.write(self.style.SUCCESS('\n=== END DEBUG REPORT ===\n'))
