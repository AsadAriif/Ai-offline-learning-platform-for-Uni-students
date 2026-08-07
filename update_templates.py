import os

template_dir = r'e:\myprojt\backend\MyApp\templates\MyApp'
static_mapping = {
    'href="index.css"': 'href="{% static \'MyApp/index.css\' %}"',
    'href="login.css"': 'href="{% static \'MyApp/login.css\' %}"',
    'href="dashboard.css"': 'href="{% static \'MyApp/dashboard.css\' %}"',
    'src="white-Logo__1_-removebg-preview.png"': 'src="{% static \'MyApp/white-Logo__1_-removebg-preview.png\' %}"',
    'src="WhatsApp_Image_2026-05-12_at_10.36.40_PM-removebg-preview.png"': 'src="{% static \'MyApp/WhatsApp_Image_2026-05-12_at_10.36.40_PM-removebg-preview.png\' %}"',
    'href="index.html"': 'href="{% url \'index\' %}"',
    'href="login.html"': 'href="{% url \'login\' %}"',
    'href="student.html"': 'href="{% url \'student_dashboard\' %}"',
    'href="teacher.html"': 'href="{% url \'teacher_dashboard\' %}"',
    'href="student-actions.html"': 'href="{% url \'student_actions\' %}"',
    'href="student-assignments.html"': 'href="{% url \'student_assignments\' %}"',
    'href="student-materials.html"': 'href="{% url \'student_materials\' %}"',
    'href="student-progress.html"': 'href="{% url \'student_progress\' %}"',
    'href="student-quiz.html"': 'href="{% url \'student_quiz\' %}"',
    'href="student-results.html"': 'href="{% url \'student_results\' %}"',
    'href="teacher-actions.html"': 'href="{% url \'teacher_actions\' %}"',
        # assignment and invite templates are disabled; mappings removed.
}

for filename in os.listdir(template_dir):
    if filename.endswith('.html'):
        filepath = os.path.join(template_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Add load static at top
        if '{% load static %}' not in content:
            content = '{% load static %}\n' + content
            
        # Replace based on mapping
        for key, value in static_mapping.items():
            content = content.replace(key, value)
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
print("Updated all templates successfully.")
