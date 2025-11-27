from django.contrib import admin
from .models import User, Course, Enrollment, DailyTask, TaskSubmission, Offer, Feedback, Payment, Certificate, Profile,Module,Lesson


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_approved', 'experience', 'qualification')
    list_filter = ('role', 'is_approved')
    actions = ['approve_instructors']

    def approve_instructors(self, request, queryset):
        count = 0
        for instructor in queryset.filter(role='instructor', is_approved=False):
            instructor.is_approved = True
            instructor.save()
            count += 1
        self.message_user(request, f"{count} instructor(s) approved successfully.")
    approve_instructors.short_description = "Approve selected instructors"

admin.site.register(Course)
admin.site.register(Enrollment)
admin.site.register(DailyTask)
admin.site.register(TaskSubmission)
admin.site.register(Offer)
admin.site.register(Feedback)
admin.site.register(Payment)
admin.site.register(Certificate)
admin.site.register(Profile)
admin.site.register(Module)
admin.site.register(Lesson)
