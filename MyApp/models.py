from django.utils import timezone
# pyrefly: ignore [missing-import]
import re
from django.db import models
# pyrefly: ignore [missing-import]
from django.contrib.auth.models import AbstractUser
import secrets
from django.conf import settings
from django.core.mail import send_mail
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.db.models.signals import post_save
from django.dispatch import receiver

# This is your Custom User model. 
# It combines User ID, Password, and Role into ONE single table in pgAdmin.
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('hod', 'Head of Department (HOD)'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone_number = models.CharField(max_length=20, blank=True, default='')

    def __str__(self):
        return f"{self.username} ({self.role})"

class Invitation(models.Model):
    email = models.EmailField()
    token = models.CharField(max_length=50, unique=True)
    course = models.CharField(max_length=100)
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_invitations')
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invite to {self.email} for {self.course}"

    def save(self, *args, **kwargs):
        if not self.token:
            # generate a short URL-safe token
            self.token = secrets.token_urlsafe(16)[:50]
        super().save(*args, **kwargs)
    # Invitation emailing functionality removed.



class Course(models.Model):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, blank=True, null=True)
    teacher = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_courses')

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class Enrollment(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.username} in {self.course.name}"


class Assignment(models.Model):
    KIND_CHOICES = [
        ('homework', 'Homework'),
        ('quiz', 'Quiz'),
        ('project', 'Project'),
    ]

    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=50, choices=KIND_CHOICES, default='homework')
    description = models.TextField(blank=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments')
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_assignments')
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # Optional file/resource attached to the assignment (pdf, ppt, etc.)
    file = models.FileField(upload_to='assignments/', blank=True, null=True)
    # Quiz-specific metadata
    quiz_type = models.CharField(
        max_length=50,
        choices=[
            ('manual', 'Manual question answer'),
            ('mcq', 'MCQ'),
            ('fillblank', 'Fill in the blanks'),
        ],
        default='manual'
    )
    assigned_student = models.ForeignKey(
        'CustomUser',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='assigned_quizzes'
    )
    # Optional deadline for student submissions
    deadline = models.DateTimeField(blank=True, null=True)


class QuizQuestion(models.Model):
    QUIZ_TYPE_CHOICES = [
        ('manual', 'Manual question answer'),
        ('mcq', 'MCQ'),
        ('fillblank', 'Fill in the blanks'),
    ]

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='quiz_questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUIZ_TYPE_CHOICES)
    options = models.JSONField(blank=True, null=True)
    blanks = models.JSONField(blank=True, null=True)
    expected_answer = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def get_display_text(self):
        if self.question_type != 'fillblank':
            return self.question_text
        text = re.sub(r'\[\[(.*?)\]\]', '_____', self.question_text)
        text = re.sub(r'_{2,}', '_____', text)
        return text

    def __str__(self):
        return f"{self.assignment.title} question {self.order + 1}"


class Material(models.Model):
    title = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='materials')
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='uploaded_materials')
    file = models.FileField(upload_to='materials/')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.course.name})"


class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='submissions')
    file = models.FileField(upload_to='submissions/', blank=True, null=True)
    answer_text = models.TextField(blank=True)
    answers = models.JSONField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    graded = models.BooleanField(default=False)
    grade = models.CharField(max_length=50, blank=True)
    marks = models.FloatField(blank=True, null=True)  # Numeric marks for manual entry
    feedback = models.TextField(blank=True)
    class Meta:
        unique_together = ('assignment', 'student')
    def __str__(self):
        return f"Submission by {self.student.username} for {self.assignment.title}"
class Message(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_messages')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='messages', blank=True, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"Message from {self.sender.username} to {self.recipient.username}"


class TeacherTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('urgent', 'Urgent'),
    ]
    hod = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_tasks')
    teacher = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='assigned_tasks')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Task for {self.teacher.username}: {self.title}"


class TeacherAttendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present (Conducted)'),
        ('absent', 'Absent / Rescheduled'),
        ('leave', 'Official Leave'),
    ]
    teacher = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='attendance_records')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    topic_covered = models.CharField(max_length=255, blank=True)
    students_present = models.PositiveIntegerField(default=0)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.teacher.username} - {self.course.name} on {self.date}"


class MarksheetSubmission(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Pending HOD Approval'),
        ('approved', 'Approved by HOD'),
        ('revision_requested', 'Revision Requested'),
    ]
    teacher = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='submitted_marksheets')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='marksheets')
    assignment = models.ForeignKey('Assignment', on_delete=models.SET_NULL, null=True, blank=True, related_name='marksheets')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='marksheets/', blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='submitted')
    hod_feedback = models.TextField(blank=True)
    total_students = models.PositiveIntegerField(default=0)
    average_score = models.FloatField(default=0.0)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.teacher.username} ({self.get_status_display()})"


class Notification(models.Model):
    PRIORITY_CHOICES = [
        ('normal', 'Standard Notice'),
        ('urgent', 'Urgent / Priority 🚨'),
        ('exam', 'Exam & Marks Notice 📑'),
        ('meeting', 'Faculty / Official Meeting 🏛️'),
    ]

    AUDIENCE_CHOICES = [
        ('individual_teacher', 'Specific Teacher'),
        ('all_teachers', 'All Faculty Members'),
        ('all_students', 'All Enrolled Students'),
        ('course_relevant', 'Relevant Course Teacher & Students'),
        ('everyone', 'Campus Wide (Everyone)'),
    ]

    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_notifications')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_notifications', null=True, blank=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    audience_type = models.CharField(max_length=30, choices=AUDIENCE_CHOICES, default='individual_teacher')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        recip = self.recipient.username if self.recipient else "Broadcast"
        return f"[{self.priority.upper()}] {self.title} -> {recip}"
