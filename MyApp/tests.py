from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from MyApp.models import CustomUser, Course, Enrollment, Assignment, QuizQuestion, Material, Submission, Message, Invitation, TeacherTask, TeacherAttendance, MarksheetSubmission, Notification

class ComprehensivePlatformTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a teacher
        self.teacher = CustomUser.objects.create_user(
            username='prof_ahmed',
            password='Password123!',
            role='teacher',
            first_name='Ahmed',
            last_name='Khan',
            phone_number='03001112233'
        )
        # Create a student
        self.student = CustomUser.objects.create_user(
            username='s1001',
            password='Password123!',
            role='student',
            first_name='Bilal',
            last_name='Raza',
            phone_number='03004445566'
        )
        # Create a course and enroll student
        self.course = Course.objects.create(name='CS101 - Intro to AI', code='CS101')
        self.enrollment = Enrollment.objects.create(student=self.student, course=self.course)
        # Create HOD
        self.hod = CustomUser.objects.create_user(
            username='hod_test',
            password='Password123!',
            role='hod',
            first_name='Dr. Muhammad',
            last_name='Arshad'
        )

    def test_01_index_page(self):
        """Test home index page loads successfully."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Baba Guru Nanak University')
        self.assertContains(response, 'AI Offline Learning Platform')

    def test_02_signup_and_validation(self):
        """Test student and teacher signup."""
        # Mismatched passwords
        res_fail = self.client.post(reverse('signup'), {
            'full_name': 'Zain Ali',
            'username': 's1002',
            'password': 'Password1',
            'password_confirm': 'Password2',
            'role': 'student',
            'phone_number': '03001234567'
        })
        self.assertEqual(res_fail.status_code, 302)
        self.assertFalse(CustomUser.objects.filter(username='s1002').exists())

        # Successful signup
        res_ok = self.client.post(reverse('signup'), {
            'full_name': 'Zain Ali',
            'username': 's1002',
            'password': 'Password123!',
            'password_confirm': 'Password123!',
            'role': 'student',
            'phone_number': '03001234567'
        })
        self.assertEqual(res_ok.status_code, 302)
        new_user = CustomUser.objects.filter(username='s1002').first()
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user.first_name, 'Zain')
        self.assertEqual(new_user.last_name, 'Ali')
        self.assertEqual(new_user.role, 'student')

    def test_03_login_and_logout(self):
        """Test authentication and role-based redirection."""
        # Invalid credentials
        res_bad = self.client.post(reverse('login'), {
            'student_id': 'prof_ahmed',
            'password': 'WrongPassword',
            'role': 'teacher'
        })
        self.assertEqual(res_bad.status_code, 200)

        # Successful teacher login
        res_teacher = self.client.post(reverse('login'), {
            'student_id': 'prof_ahmed',
            'password': 'Password123!',
            'role': 'teacher'
        })
        self.assertRedirects(res_teacher, reverse('teacher_dashboard'))

        # Logout
        res_logout = self.client.get(reverse('logout'))
        self.assertRedirects(res_logout, reverse('login'))

        # Successful student login
        res_student = self.client.post(reverse('login'), {
            'student_id': 's1001',
            'password': 'Password123!',
            'role': 'student'
        })
        self.assertRedirects(res_student, reverse('student_dashboard'))

    def test_04_profile_management(self):
        """Test updating profile and changing password."""
        self.client.login(username='s1001', password='Password123!')
        res_update = self.client.post(reverse('profile'), {
            'first_name': 'Bilal Updated',
            'last_name': 'Raza Updated',
            'password': 'NewPassword123!',
            'password_confirm': 'NewPassword123!'
        })
        self.assertRedirects(res_update, reverse('profile'))
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, 'Bilal Updated')
        self.assertTrue(self.student.check_password('NewPassword123!'))

    def test_05_teacher_enroll_students(self):
        """Test teacher inviting and bulk enrolling students."""
        self.client.login(username='prof_ahmed', password='Password123!')
        res = self.client.post(reverse('teacher_invite'), {
            'course_name': 'CS102 - Data Structures',
            'course_code': 'CS102',
            'students': 's2001,Pass123,Farhan Khan\ns2002,Pass456,Usman Tariq',
            'student_roll': '',
            'student_password': '',
            'student_name': ''
        })
        self.assertRedirects(res, reverse('teacher_invite'))
        s2001 = CustomUser.objects.filter(username='s2001').first()
        self.assertIsNotNone(s2001)
        self.assertEqual(s2001.first_name, 'Farhan')
        self.assertEqual(s2001.last_name, 'Khan')
        cs102 = Course.objects.filter(name='CS102 - Data Structures').first()
        self.assertIsNotNone(cs102)
        self.assertTrue(Enrollment.objects.filter(student=s2001, course=cs102).exists())

    def test_06_teacher_materials_and_pastpapers(self):
        """Test uploading and deleting materials and past papers."""
        self.client.login(username='prof_ahmed', password='Password123!')
        test_file = SimpleUploadedFile("lecture1.txt", b"Introduction to Neural Networks notes", content_type="text/plain")
        
        # Upload lecture notes
        res_mat = self.client.post(reverse('teacher_materials'), {
            'course': self.course.name,
            'title': 'Lecture 1 Notes',
            'description': 'Introductory lecture notes',
            'file': test_file
        })
        self.assertRedirects(res_mat, reverse('teacher_materials'))
        mat = Material.objects.filter(title='Lecture 1 Notes', uploaded_by=self.teacher).first()
        self.assertIsNotNone(mat)
        self.assertNotEqual(mat.description, 'past_paper')

        # Upload past paper
        pp_file = SimpleUploadedFile("midterm2025.txt", b"Midterm Examination CS101 2025", content_type="text/plain")
        res_pp = self.client.post(reverse('teacher_pastpaper'), {
            'course': self.course.name,
            'title': 'Midterm Exam 2025',
            'file': pp_file
        })
        self.assertRedirects(res_pp, reverse('teacher_pastpaper'))
        pp = Material.objects.filter(title='Midterm Exam 2025', description='past_paper').first()
        self.assertIsNotNone(pp)

        # Delete material
        res_del_mat = self.client.post(reverse('delete_material', args=[mat.id]))
        self.assertRedirects(res_del_mat, reverse('teacher_materials'))
        self.assertFalse(Material.objects.filter(id=mat.id).exists())

        # Delete past paper
        res_del_pp = self.client.post(reverse('delete_pastpaper', args=[pp.id]))
        self.assertRedirects(res_del_pp, reverse('teacher_pastpaper'))
        self.assertFalse(Material.objects.filter(id=pp.id).exists())

    def test_07_teacher_create_assignment_and_quiz(self):
        """Test creating an assignment and an interactive quiz."""
        self.client.login(username='prof_ahmed', password='Password123!')
        
        # Homework assignment
        res_hw = self.client.post(reverse('teacher_assignment'), {
            'form_type': 'assignment',
            'course': self.course.name,
            'title': 'Homework 1: Machine Learning Basics',
            'kind': 'homework',
            'description': 'Implement gradient descent algorithm in Python.',
            'publish': '1'
        })
        self.assertRedirects(res_hw, reverse('teacher_assignment'))
        hw = Assignment.objects.filter(title='Homework 1: Machine Learning Basics').first()
        self.assertIsNotNone(hw)
        self.assertTrue(hw.published)

        # Quiz with MCQ and manual questions
        res_quiz = self.client.post(reverse('teacher_assignment'), {
            'form_type': 'quiz',
            'course': self.course.name,
            'title': 'Quiz 1: AI Concepts',
            'quiz_type': 'mcq',
            'question_count': '2',
            'question_text_0': 'What does AI stand for?',
            'question_option_0_A': 'Artificial Intelligence',
            'question_option_0_B': 'Automated Internet',
            'question_option_0_C': 'Advanced Interface',
            'question_option_0_D': 'Apple Inc',
            'question_correct_0': 'A',
            'question_text_1': 'Which algorithm is used for classification?',
            'question_option_1_A': 'Linear Regression',
            'question_option_1_B': 'Logistic Regression',
            'question_option_1_C': 'K-Means',
            'question_option_1_D': 'PCA',
            'question_correct_1': 'B',
            'publish': '1'
        })
        self.assertRedirects(res_quiz, reverse('teacher_assignment'))
        quiz = Assignment.objects.filter(title='Quiz 1: AI Concepts').first()
        self.assertIsNotNone(quiz)
        self.assertEqual(quiz.quiz_questions.count(), 2)

        # Verify notification message was dispatched to enrolled student
        msg = Message.objects.filter(recipient=self.student, course=self.course).first()
        self.assertIsNotNone(msg)

    def test_08_student_quiz_and_homework_submission(self):
        """Test student attempting quiz and submitting homework."""
        # Create homework and quiz
        hw = Assignment.objects.create(
            title='Project 1',
            kind='project',
            course=self.course,
            created_by=self.teacher,
            published=True
        )
        quiz = Assignment.objects.create(
            title='Quick Quiz',
            kind='quiz',
            quiz_type='mcq',
            course=self.course,
            created_by=self.teacher,
            published=True
        )
        q1 = QuizQuestion.objects.create(
            assignment=quiz,
            question_text='What is 2 + 2?',
            question_type='mcq',
            options={'A': '3', 'B': '4', 'C': '5', 'D': '6'},
            expected_answer='B',
            order=0
        )

        self.client.login(username='s1001', password='Password123!')

        # Submit homework
        res_sub_hw = self.client.post(reverse('submit_assignment', args=[hw.id]), {
            'answer_text': 'Here is my project code submission.'
        })
        self.assertRedirects(res_sub_hw, reverse('student_assignments'))
        sub_hw = Submission.objects.filter(assignment=hw, student=self.student).first()
        self.assertIsNotNone(sub_hw)
        self.assertEqual(sub_hw.answer_text, 'Here is my project code submission.')

        # Submit quiz
        res_sub_quiz = self.client.post(reverse('submit_assignment', args=[quiz.id]), {
            f'question_{q1.id}': 'B'
        })
        self.assertRedirects(res_sub_quiz, reverse('student_assignments'))
        sub_quiz = Submission.objects.filter(assignment=quiz, student=self.student).first()
        self.assertIsNotNone(sub_quiz)
        self.assertEqual(sub_quiz.answers.get(str(q1.id)), 'B')

    def test_09_teacher_submissions_grading_and_results(self):
        """Test teacher viewing submissions, grading, and publishing results."""
        hw = Assignment.objects.create(
            title='Lab 1',
            kind='homework',
            course=self.course,
            created_by=self.teacher,
            published=True
        )
        sub = Submission.objects.create(
            assignment=hw,
            student=self.student,
            answer_text='Lab 1 work completed.'
        )

        self.client.login(username='prof_ahmed', password='Password123!')
        
        # Grade in teacher_submissions
        res_grade = self.client.post(reverse('teacher_submissions', args=[hw.id]), {
            f'marks_{sub.id}': '95',
            f'grade_{sub.id}': 'A+',
            f'feedback_{sub.id}': 'Excellent work!'
        })
        self.assertRedirects(res_grade, reverse('teacher_submissions', args=[hw.id]))
        sub.refresh_from_db()
        self.assertEqual(sub.marks, 95.0)
        self.assertEqual(sub.grade, 'A+')
        self.assertTrue(sub.graded)

        # Grade and publish in teacher_results
        res_results = self.client.post(reverse('teacher_results'), {
            'assignment_id': str(hw.id),
            f'marks_{hw.id}_{self.student.id}': '98',
            f'grade_{hw.id}_{self.student.id}': 'A+',
            f'feedback_{hw.id}_{self.student.id}': 'Updated top score',
            'publish': '1'
        })
        self.assertRedirects(res_results, reverse('teacher_results'))
        sub.refresh_from_db()
        self.assertEqual(sub.marks, 98.0)

    def test_10_student_views_and_progress(self):
        """Test student dashboard, actions, materials, quiz, results, and progress pages."""
        self.client.login(username='s1001', password='Password123!')

        pages = [
            'student_dashboard',
            'student_actions',
            'student_assignments',
            'student_materials',
            'student_pastpapers',
            'student_quiz',
            'student_results',
            'student_progress',
        ]
        for page_name in pages:
            res = self.client.get(reverse(page_name))
            self.assertEqual(res.status_code, 200, f"Page {page_name} returned status {res.status_code}")

    def test_11_ai_detector_endpoints(self):
        """Test AI detector endpoints."""
        self.client.login(username='prof_ahmed', password='Password123!')

        # 1. teacher_detect page
        res_get = self.client.get(reverse('teacher_detect'))
        self.assertEqual(res_get.status_code, 200)

        # Post sample document
        sample_doc = SimpleUploadedFile("essay.txt", b"Artificial intelligence is transforming modern educational frameworks through intelligent personalized learning.", content_type="text/plain")
        res_post = self.client.post(reverse('teacher_detect'), {'file': sample_doc})
        self.assertEqual(res_post.status_code, 200)
        self.assertIn('result', res_post.context)
        self.assertIn(res_post.context['result']['label'], ['AI', 'Human'])

        # 2. detect_submission endpoint
        hw = Assignment.objects.create(
            title='Essay Test',
            kind='homework',
            course=self.course,
            created_by=self.teacher,
            published=True
        )
        sub = Submission.objects.create(
            assignment=hw,
            student=self.student,
            answer_text='This is an essay written by a student for the computer science course.'
        )
        res_detect_sub = self.client.post(reverse('detect_submission', args=[sub.id]))
        self.assertEqual(res_detect_sub.status_code, 200)
        json_data = res_detect_sub.json()
        self.assertIn('label', json_data)
        self.assertIn('confidence', json_data)

    def test_12_hod_login_and_dashboard(self):
        """Test HOD login and dashboard overview metrics."""
        res = self.client.post(reverse('login'), {
            'student_id': 'hod_test',
            'password': 'Password123!',
            'role': 'hod'
        })
        self.assertRedirects(res, reverse('hod_dashboard'))

        res_dash = self.client.get(reverse('hod_dashboard'))
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn('total_faculty', res_dash.context)
        self.assertIn('total_courses', res_dash.context)
        self.assertIn('total_students', res_dash.context)
        self.assertContains(res_dash, 'Head of Department')

    def test_13_hod_course_allocation_and_restriction(self):
        """Test HOD allocating courses and teacher course restriction."""
        self.client.login(username='hod_test', password='Password123!')

        # HOD creates course and allocates to teacher
        res_create = self.client.post(reverse('hod_courses'), {
            'action': 'create',
            'name': 'CS301 - Operating Systems',
            'code': 'CS301',
            'teacher_id': str(self.teacher.id)
        })
        self.assertRedirects(res_create, reverse('hod_courses'))
        cs301 = Course.objects.filter(name='CS301 - Operating Systems').first()
        self.assertIsNotNone(cs301)
        self.assertEqual(cs301.teacher, self.teacher)

        # Teacher logs in
        self.client.login(username='prof_ahmed', password='Password123!')

        # Teacher tries to invite student to an unassigned course
        res_unauth = self.client.post(reverse('teacher_invite'), {
            'course_name': 'Unauthorized Course 999',
            'students': 's4001,Pass123,Imran Khan'
        })
        self.assertRedirects(res_unauth, reverse('teacher_invite'))
        self.assertFalse(CustomUser.objects.filter(username='s4001').exists())

        # Teacher invites student to their assigned course CS301
        res_auth = self.client.post(reverse('teacher_invite'), {
            'course_name': 'CS301 - Operating Systems',
            'students': 's4001,Pass123,Imran Khan'
        })
        self.assertRedirects(res_auth, reverse('teacher_invite'))
        s4001 = CustomUser.objects.filter(username='s4001').first()
        self.assertIsNotNone(s4001)
        self.assertTrue(Enrollment.objects.filter(student=s4001, course=cs301).exists())

    def test_14_hod_task_assignment_and_teacher_update(self):
        """Test HOD assigning duties to teacher and teacher updating status."""
        self.client.login(username='hod_test', password='Password123!')

        res_task = self.client.post(reverse('hod_tasks'), {
            'action': 'create_task',
            'teacher_id': str(self.teacher.id),
            'course_id': str(self.course.id),
            'title': 'Prepare Final Exam Paper',
            'description': 'Follow official university paper format.',
            'due_date': '2026-12-01',
            'priority': 'urgent'
        })
        self.assertRedirects(res_task, reverse('hod_tasks'))
        task = TeacherTask.objects.filter(title='Prepare Final Exam Paper').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.priority, 'urgent')

        # Teacher views and updates task in teacher_attendance
        self.client.login(username='prof_ahmed', password='Password123!')
        res_update = self.client.post(reverse('teacher_attendance'), {
            'action': 'update_task',
            'task_id': str(task.id),
            'status': 'completed'
        })
        self.assertRedirects(res_update, reverse('teacher_attendance'))
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')

    def test_15_teacher_attendance_logging(self):
        """Test teacher logging class conduction and HOD inspecting records."""
        self.client.login(username='prof_ahmed', password='Password123!')

        res_log = self.client.post(reverse('teacher_attendance'), {
            'action': 'log_lecture',
            'course_id': str(self.course.id),
            'date': '2026-11-02',
            'status': 'present',
            'topic_covered': 'Neural Networks and Deep Learning',
            'students_present': '45',
            'remarks': 'All lab exercises executed successfully.'
        })
        self.assertRedirects(res_log, reverse('teacher_attendance'))
        log_entry = TeacherAttendance.objects.filter(teacher=self.teacher, topic_covered__icontains='Neural Networks').first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.students_present, 45)

        # HOD inspects attendance records
        self.client.login(username='hod_test', password='Password123!')
        res_hod = self.client.get(reverse('hod_attendance'))
        self.assertEqual(res_hod.status_code, 200)
        self.assertContains(res_hod, 'Neural Networks and Deep Learning')

    def test_16_marksheet_submission_and_hod_approval(self):
        """Test teacher submitting marksheet to HOD and HOD approving it."""
        self.client.login(username='prof_ahmed', password='Password123!')

        res_ms = self.client.post(reverse('teacher_results'), {
            'action': 'submit_to_hod',
            'course_id': str(self.course.id),
            'title': 'Midterm Exam Official Marksheet',
        })
        self.assertRedirects(res_ms, reverse('teacher_results'))
        ms = MarksheetSubmission.objects.filter(title='Midterm Exam Official Marksheet').first()
        self.assertIsNotNone(ms)
        self.assertEqual(ms.status, 'submitted')

        # HOD approves marksheet
        self.client.login(username='hod_test', password='Password123!')
        res_approve = self.client.post(reverse('hod_marksheets'), {
            'marksheet_id': str(ms.id),
            'status': 'approved',
            'hod_feedback': 'Marksheet verified and approved for publication.'
        })
        self.assertRedirects(res_approve, reverse('hod_marksheets'))
        ms.refresh_from_db()
        self.assertEqual(ms.status, 'approved')
        self.assertEqual(ms.hod_feedback, 'Marksheet verified and approved for publication.')

    def test_17_hod_student_roster_csv_and_teacher_import(self):
        """Test downloading HOD roster CSV and teacher bulk uploading roster file."""
        self.client.login(username='hod_test', password='Password123!')

        # Download roster CSV
        res_csv = self.client.get(reverse('hod_student_roster') + f'?course_id={self.course.id}')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv['Content-Type'], 'text/csv')

        # Teacher uploads roster file to enroll students
        self.client.login(username='prof_ahmed', password='Password123!')
        csv_data = b"Student_ID,Password,Full_Name,Email,Phone_Number,Course_Name\ns5001,PassSecret1,Bilal Hassan,b.hassan@bgnu.edu.pk,03001122334,CS101 - Intro to AI\ns5002,PassSecret2,Zainab Bibi,z.bibi@bgnu.edu.pk,03002233445,CS101 - Intro to AI"
        roster_file = SimpleUploadedFile("roster.csv", csv_data, content_type="text/csv")

        # Assign course to teacher first so restriction allows it
        self.course.teacher = self.teacher
        self.course.save()

        res_upload = self.client.post(reverse('teacher_invite'), {
            'course_name': self.course.name,
            'roster_file': roster_file
        })
        self.assertRedirects(res_upload, reverse('teacher_invite'))
        s5001 = CustomUser.objects.filter(username='s5001').first()
        self.assertIsNotNone(s5001)
        self.assertEqual(s5001.first_name, 'Bilal')
        self.assertEqual(s5001.email, 'b.hassan@bgnu.edu.pk')
        self.assertTrue(s5001.check_password('PassSecret1'))
        self.assertTrue(Enrollment.objects.filter(student=s5001, course=self.course).exists())

    def test_18_hod_creates_another_hod_and_faculty(self):
        """Test HOD creating another HOD account and faculty member."""
        self.client.login(username='hod_test', password='Password123!')

        # Create another HOD ("Aik HOD differnet HOD bhi add kr sktha hai")
        res_hod = self.client.post(reverse('hod_manage_users'), {
            'action': 'create_hod',
            'username': 'hod_assistant',
            'password': 'Pass1234!',
            'full_name': 'Dr. Tariq Ali',
            'email': 'tariq.ali@bgnu.edu.pk',
            'phone_number': '03009988776'
        })
        self.assertRedirects(res_hod, reverse('hod_manage_users'))
        new_hod = CustomUser.objects.filter(username='hod_assistant').first()
        self.assertIsNotNone(new_hod)
        self.assertEqual(new_hod.role, 'hod')
        self.assertEqual(new_hod.first_name, 'Dr.')

        # Create new faculty member
        res_fac = self.client.post(reverse('hod_manage_users'), {
            'action': 'create_teacher',
            'username': 'prof_salman',
            'password': 'Pass1234!',
            'full_name': 'Salman Farooq',
            'email': 'salman@bgnu.edu.pk',
            'phone_number': '03005544332',
            'course_id': str(self.course.id)
        })
        self.assertRedirects(res_fac, reverse('hod_manage_users'))
        new_fac = CustomUser.objects.filter(username='prof_salman').first()
        self.assertIsNotNone(new_fac)
        self.assertEqual(new_fac.role, 'teacher')
        self.course.refresh_from_db()
        self.assertEqual(self.course.teacher, new_fac)

    def test_19_teacher_multi_course_selection_and_isolation(self):
        """Test teacher with multiple HOD courses: choosing 1, 2, or all courses, and course isolation."""
        # Create unassigned course
        unassigned_c = Course.objects.create(name='Physics 101 - General', code='PHY101')

        # HOD assigns two distinct courses to teacher
        course_a = Course.objects.create(name='CS401 - Cloud Computing', code='CS401', teacher=self.teacher)
        course_b = Course.objects.create(name='CS402 - Mobile App Dev', code='CS402', teacher=self.teacher)

        self.client.login(username='prof_ahmed', password='Password123!')

        # 1. Verify in all teacher views that ONLY assigned courses are shown, not unassigned_c
        for view_name in ['teacher_assignment', 'teacher_materials', 'teacher_pastpaper']:
            res = self.client.get(reverse(view_name))
            self.assertEqual(res.status_code, 200)
            courses_in_view = res.context['courses']
            self.assertIn(course_a, courses_in_view)
            self.assertIn(course_b, courses_in_view)
            self.assertNotIn(unassigned_c, courses_in_view)

        # 2. Teacher enrolls student choosing ONLY Course A
        res_single = self.client.post(reverse('teacher_invite'), {
            'selected_courses': [course_a.name],
            'students': 's6001,Pass123,Student One'
        })
        self.assertRedirects(res_single, reverse('teacher_invite'))
        s6001 = CustomUser.objects.filter(username='s6001').first()
        self.assertIsNotNone(s6001)
        self.assertTrue(Enrollment.objects.filter(student=s6001, course=course_a).exists())
        self.assertFalse(Enrollment.objects.filter(student=s6001, course=course_b).exists())

        # 3. Teacher enrolls student choosing BOTH Course A and Course B (2 courses)
        res_multi = self.client.post(reverse('teacher_invite'), {
            'selected_courses': [course_a.name, course_b.name],
            'students': 's6002,Pass123,Student Two'
        })
        self.assertRedirects(res_multi, reverse('teacher_invite'))
        s6002 = CustomUser.objects.filter(username='s6002').first()
        self.assertIsNotNone(s6002)
        self.assertTrue(Enrollment.objects.filter(student=s6002, course=course_a).exists())
        self.assertTrue(Enrollment.objects.filter(student=s6002, course=course_b).exists())

        # 4. Teacher enrolls student choosing ALL assigned courses
        res_all = self.client.post(reverse('teacher_invite'), {
            'all_courses': '1',
            'students': 's6003,Pass123,Student Three'
        })
        self.assertRedirects(res_all, reverse('teacher_invite'))
        s6003 = CustomUser.objects.filter(username='s6003').first()
        self.assertIsNotNone(s6003)
        self.assertTrue(Enrollment.objects.filter(student=s6003, course=course_a).exists())
        self.assertTrue(Enrollment.objects.filter(student=s6003, course=course_b).exists())
        self.assertFalse(Enrollment.objects.filter(student=s6003, course=unassigned_c).exists())

        # 5. Teacher tries to upload material to an unassigned course -> blocked
        test_file = SimpleUploadedFile("notes.txt", b"Notes content", content_type="text/plain")
        res_unauth_mat = self.client.post(reverse('teacher_materials'), {
            'course': unassigned_c.name,
            'title': 'Unauthorized Notes',
            'file': test_file
        })
        self.assertRedirects(res_unauth_mat, reverse('teacher_materials'))
        self.assertFalse(Material.objects.filter(title='Unauthorized Notes').exists())

    def test_20_hod_notifications_and_broadcast(self):
        """
        Verify HOD Announcement Broadcast options:
        1. Specific Teacher
        2. All Teachers
        3. All Students
        4. Relevant Teacher and Students of a specific course
        """
        # Create second teacher and second student
        teacher2 = CustomUser.objects.create_user(username='prof_t2', password='Password123!', role='teacher')
        student2 = CustomUser.objects.create_user(username='s1002', password='Password123!', role='student')
        
        # Course setup: assign self.course to self.teacher, self.student is enrolled
        self.course.teacher = self.teacher
        self.course.save()

        # Unauthenticated user redirected to login
        res_unauth = self.client.get(reverse('hod_notifications'))
        self.assertEqual(res_unauth.status_code, 302)
        self.assertIn('/login/', res_unauth.url)

        # Non-HOD authenticated user denied access
        self.client.login(username='s1001', password='Password123!')
        res_denied = self.client.get(reverse('hod_notifications'))
        self.assertEqual(res_denied.status_code, 302)
        self.client.logout()

        # Login as HOD
        self.client.login(username='hod_test', password='Password123!')
        res_get = self.client.get(reverse('hod_notifications'))
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, 'Official Announcements')

        # 1. Dispatch to Individual Teacher
        res1 = self.client.post(reverse('hod_notifications'), {
            'audience_type': 'individual_teacher',
            'teacher_id': self.teacher.id,
            'title': 'Faculty Evaluation Form',
            'message': 'Please complete your semester evaluation by Friday.',
            'priority': 'urgent',
        })
        self.assertRedirects(res1, reverse('hod_notifications'))
        self.assertTrue(Notification.objects.filter(recipient=self.teacher, title='Faculty Evaluation Form', priority='urgent').exists())
        self.assertFalse(Notification.objects.filter(recipient=teacher2, title='Faculty Evaluation Form').exists())

        # 2. Dispatch to All Teachers
        res2 = self.client.post(reverse('hod_notifications'), {
            'audience_type': 'all_teachers',
            'title': 'Department Meeting Scheduled',
            'message': 'All faculty are requested to attend the meeting at 3 PM.',
            'priority': 'meeting',
        })
        self.assertRedirects(res2, reverse('hod_notifications'))
        self.assertTrue(Notification.objects.filter(recipient=self.teacher, title='Department Meeting Scheduled').exists())
        self.assertTrue(Notification.objects.filter(recipient=teacher2, title='Department Meeting Scheduled').exists())
        self.assertFalse(Notification.objects.filter(recipient=self.student, title='Department Meeting Scheduled').exists())

        # 3. Dispatch to All Students
        res3 = self.client.post(reverse('hod_notifications'), {
            'audience_type': 'all_students',
            'title': 'Final Term Exam Schedule',
            'message': 'Final exams start next Monday. Check your roll number slips.',
            'priority': 'exam',
        })
        self.assertRedirects(res3, reverse('hod_notifications'))
        self.assertTrue(Notification.objects.filter(recipient=self.student, title='Final Term Exam Schedule').exists())
        self.assertTrue(Notification.objects.filter(recipient=student2, title='Final Term Exam Schedule').exists())
        self.assertFalse(Notification.objects.filter(recipient=self.teacher, title='Final Term Exam Schedule').exists())

        # 4. Dispatch to Relevant Course Teacher and Students
        res4 = self.client.post(reverse('hod_notifications'), {
            'audience_type': 'course_relevant',
            'course_id': self.course.id,
            'title': 'AI Project Submission Guidelines',
            'message': 'Follow the standard AI offline submission template.',
            'priority': 'normal',
        })
        self.assertRedirects(res4, reverse('hod_notifications'))
        # Allocated teacher and enrolled student receive it
        self.assertTrue(Notification.objects.filter(recipient=self.teacher, course=self.course, title='AI Project Submission Guidelines').exists())
        self.assertTrue(Notification.objects.filter(recipient=self.student, course=self.course, title='AI Project Submission Guidelines').exists())
        # Unrelated student2 does NOT receive it
        self.assertFalse(Notification.objects.filter(recipient=student2, title='AI Project Submission Guidelines').exists())

    def test_21_notifications_inbox_and_read_status(self):
        """
        Verify Notification Inbox, unread count, and mark-as-read functionality.
        """
        # Create notice for self.student
        notif = Notification.objects.create(
            sender=self.hod,
            recipient=self.student,
            title='Campus ID Card Renewal',
            message='Please visit the registrar office for renewal.',
            priority='normal'
        )

        self.client.login(username='s1001', password='Password123!')
        res_inbox = self.client.get(reverse('notifications_list'))
        self.assertEqual(res_inbox.status_code, 200)
        self.assertContains(res_inbox, 'Campus ID Card Renewal')
        self.assertEqual(res_inbox.context['unread_count'], 1)

        # Mark single notice as read
        res_read = self.client.get(reverse('mark_notification_read', args=[notif.id]))
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

        # Create another notice and test mark all read
        notif2 = Notification.objects.create(
            sender=self.hod,
            recipient=self.student,
            title='Library Book Return Notice',
            message='Please return all books before finals.',
            priority='urgent'
        )
        self.assertFalse(notif2.is_read)
        res_read_all = self.client.get(reverse('mark_all_notifications_read'))
        notif2.refresh_from_db()
        self.assertTrue(notif2.is_read)

    def test_22_live_gemini_ai_chatbot(self):
        """
        Verify live Gemini AI Study Tutor chatbot endpoint.
        """
        import json

        # 1. Reject GET
        res_get = self.client.get(reverse('ai_chatbot_api'))
        self.assertEqual(res_get.status_code, 405)

        # 2. Empty query validation
        res_empty = self.client.post(
            reverse('ai_chatbot_api'),
            data=json.dumps({'message': ''}),
            content_type='application/json'
        )
        self.assertEqual(res_empty.status_code, 200)
        self.assertIn('Please enter', res_empty.json().get('reply', ''))

        # 3. Live query with Gemini API key
        res_query = self.client.post(
            reverse('ai_chatbot_api'),
            data=json.dumps({'message': 'Explain Python in 1 sentence for BGNU students.'}),
            content_type='application/json'
        )
        self.assertEqual(res_query.status_code, 200)
        reply = res_query.json().get('reply', '')
        self.assertTrue(len(reply) > 10)
