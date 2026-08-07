# pyrefly: ignore [missing-import]
from django.contrib import admin
# pyrefly: ignore [missing-import]
from django.contrib.auth.admin import UserAdmin
# pyrefly: ignore [missing-import]
from .models import CustomUser
from .models import Course, Enrollment, Assignment
from .models import Material, Submission, Message

# Register your CustomUser in the admin
class CustomUserAdmin(UserAdmin):
    # Add the role field to the admin display
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('role',)}),
    )
    list_display = ['username', 'email', 'role', 'is_staff']

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Course)
admin.site.register(Enrollment)
admin.site.register(Assignment)
admin.site.register(Material)
admin.site.register(Submission)
admin.site.register(Message)