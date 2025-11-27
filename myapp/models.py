from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal

class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('instructor', 'Instructor'),
        ('admin', 'Admin'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Instructor-specific fields
    certificate = models.FileField(upload_to='instructor_certificates/', null=True, blank=True)
    experience = models.CharField(max_length=200, blank=True, null=True)
    qualification = models.CharField(max_length=200, blank=True, null=True)
    is_approved = models.BooleanField(default=False)  # Admin approval

    def __str__(self):
        status = "✅" if self.is_approved else "⏳"
        return f"{self.username} ({self.role}) {status}"
    

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True)
    qualification = models.CharField(max_length=100, blank=True, null=True)  # for instructors
    phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} Profile"


class Course(models.Model):
    instructor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'instructor', 'is_approved': True}
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)   
    image = models.ImageField(upload_to='courses/', null=True, blank=True)
    course_duration_months = models.PositiveIntegerField(default=6)  
    created_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def enrolled_students(self):
        return [enrollment.student for enrollment in self.enrollments.all()]

    def __str__(self):
        return self.title
    
    def get_final_price(self, user=None):
        from myapp.models import Enrollment
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal

        # If no user → no offer
        if not user or not user.is_authenticated:
            return self.price

        # If user already enrolled in THIS course → no offer
        if Enrollment.objects.filter(student=user, course=self).exists():
            return self.price

        # Get user's first-ever enrollment date
        first_enrolled = (
            Enrollment.objects
            .filter(student=user)
            .order_by('enrolled_on')
            .values_list('enrolled_on', flat=True)
            .first()
        )

        # If user has no previous enrollments → no offer
        if not first_enrolled:
            return self.price

        # Offer valid for 7 days
        offer_end = first_enrolled + timedelta(days=7)

        if timezone.now() <= offer_end:
            # Apply 20% discount
            discounted = self.price * Decimal("0.80")
            return discounted.quantize(Decimal("0.01"))

        return self.price



class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_on = models.DateTimeField(auto_now_add=True)
    expires_on = models.DateTimeField(null=True, blank=True)
    progress = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.username} → {self.course.title}"


class DailyTask(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    question = models.TextField(blank=True, null=True)  # 🆕 New field
    assigned_on = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.course.title} - {self.title}"



class TaskSubmission(models.Model):
    task = models.ForeignKey(DailyTask, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    submission_file = models.FileField(upload_to='tasks/')
    feedback = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='pending'
    )
    submitted_on = models.DateTimeField(auto_now_add=True)
    # keep history / allow resubmission: link to previous submission
    previous_submission = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='resubmissions')

    def __str__(self):
        return f"{self.student.username} - {self.task.title} ({self.status})"


class Offer(models.Model):
    title = models.CharField(max_length=200)
    discount_percent = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.discount_percent}%)"


class Feedback(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(default=5)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} → {self.course.title}"


class Payment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    order_id = models.CharField(max_length=100, null=True, blank=True)  # Razorpay order_id
    payment_id = models.CharField(max_length=100, null=True, blank=True)  # Razorpay payment_id
    transaction_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")],
        default="pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {self.course.title} ({self.status})"



class Certificate(models.Model):
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='certificates'
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    issue_date = models.DateField(auto_now_add=True)
    certificate_id = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f"Certificate - {self.student.username} - {self.course.title}"


# Course structure
class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="lessons", null=True, blank=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="lessons", null=True, blank=True)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)

    # 🔹 YouTube video link (auto-saved after YouTube API upload)
    youtube_video_url = models.URLField(
        blank=True,
        null=True,
        help_text="Uploaded or linked YouTube video URL"
    )

    # 🔹 Optional PDF upload for study materials
    pdf_file = models.FileField(
        upload_to='lessons/pdfs/',
        blank=True,
        null=True,
        help_text="Upload supporting PDF study material"
    )

    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.module.title} - {self.title}"


    def __str__(self):
        return f"{self.module.title} - {self.title}"


class Quiz(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="quizzes")
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    correct_option = models.CharField(max_length=255)

    def __str__(self):
        return self.text[:50]


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=255)

    def __str__(self):
        return self.text


class StudentQuizAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)


# Live sessions
class LiveSession(models.Model):
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="live_sessions")
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    topic = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    duration = models.IntegerField(default=60)
    zoom_meeting_id = models.CharField(max_length=50, null=True, blank=True)
    join_url = models.URLField(max_length=1000)
    start_url = models.URLField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.topic} ({self.course.title})"


# Chatbot placeholder (store questions and responses)
class ChatMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
     
class Notification(models.Model):
    NOTIF_TYPES = [
        ('task', 'Task'),
        ('live', 'Live Class'),
        ('generic', 'Generic'),
    ]
    recipient = models.ForeignKey(User, related_name='notifications', on_delete=models.CASCADE)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)  # who triggered it, e.g. instructor
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    notif_type = models.CharField(max_length=20, choices=NOTIF_TYPES, default='generic')
    url = models.CharField(max_length=512, blank=True)  # frontend route to open on click
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']



class LessonCompletion(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'lesson')  # ✅ prevent duplicate completions

    def __str__(self):
        return f"{self.student.username} completed {self.lesson.title}"


User = get_user_model()

class ChatRoom(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="chatrooms")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="student_chats")
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="instructor_chats")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ChatRoom #{self.id} ({self.student.username} ↔ {self.instructor.username})"


class Message(models.Model):
    chatroom = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.sender.username}: {self.content[:20]}"