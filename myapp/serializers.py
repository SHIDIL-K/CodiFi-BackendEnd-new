from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from rest_framework import serializers
from django.utils import timezone
from .models import (
    LessonCompletion, Notification, Option, Question, StudentQuizAttempt, User, Course, Enrollment, DailyTask, TaskSubmission, Offer, Feedback, Payment,Profile,
    Certificate, Module, Lesson, Quiz, LiveSession, ChatMessage, Message, ChatRoom
)
from django.contrib.auth import get_user_model

UserModel = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'profile_picture', "certificate", 'bio', 'phone', 'experience', 'qualification', 'is_approved']


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    profile_picture = serializers.ImageField(source='user.profile_picture', required=False)
    is_approved = serializers.BooleanField(source='user.is_approved', read_only=True)

    class Meta:
        model = Profile
        fields = [
            'username', 'email', 'role', 'profile_picture',
            'bio', 'qualification', 'phone', 'is_approved'
        ]



class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        fields = ['username', 'email', 'password', 'role', 'certificate', 'experience', 'qualification']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        role = validated_data.get('role', 'student')
        user = UserModel.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=role,
            certificate=validated_data.get('certificate'),
            experience=validated_data.get('experience'),
            qualification=validated_data.get('qualification'),
        )
        if role == 'instructor':
            user.is_approved = False
        user.save()
        return user


class CourseSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.username', read_only=True)

    has_offer = serializers.SerializerMethodField()
    discount_price = serializers.SerializerMethodField()
    offer_expires = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'price', 'image','course_duration_months', 
            'instructor', 'instructor_name', 'created_at',
            'has_offer', 'discount_price', 'offer_expires'
        ]
        read_only_fields = ['created_at', 'instructor_name']

    # ✅ Get the date the user FIRST enrolled in ANY course
    def _first_enrollment_date(self, user):
        if not user or not user.is_authenticated:
            return None

        return (
            Enrollment.objects
            .filter(student=user)
            .order_by('enrolled_on')
            .values_list('enrolled_on', flat=True)
            .first()
        )

    # ✅ NEW: Check that user is NOT enrolled in this course
    def _is_user_enrolled_in_this_course(self, user, course):
        if not user or not user.is_authenticated:
            return False

        return Enrollment.objects.filter(student=user, course=course).exists()

    # ✅ MAIN OFFER LOGIC
    def get_has_offer(self, course):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        # ❌ user has no enrollment → no offer anywhere
        first_enrolled_at = self._first_enrollment_date(user)
        if not first_enrolled_at:
            return False

        # ✅ user enrolled in THIS exact course → NO OFFER
        if self._is_user_enrolled_in_this_course(user, course):
            return False

        # ✅ offer window: 7 days after first enrollment
        offer_end = first_enrolled_at + timedelta(days=7)
        return timezone.now() <= offer_end

    def get_discount_price(self, course):
        if not self.get_has_offer(course):
            return None

        discounted = (course.price * Decimal("0.80")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{discounted}"

    def get_offer_expires(self, course):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        first_enrolled_at = self._first_enrollment_date(user)
        if not first_enrolled_at:
            return None

        return (first_enrolled_at + timedelta(days=7)).isoformat()

        


# serializers.py (replace only the EnrollmentSerializer with this)

class EnrollmentSerializer(serializers.ModelSerializer):
    student = serializers.CharField(source='student.username', read_only=True)
    email = serializers.EmailField(source='student.email', read_only=True)
    # remove: course = CourseSerializer(read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'course', 'enrolled_on', 'progress', 'email']
        read_only_fields = ['enrolled_on', 'progress']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # ✅ forward the same context (so CourseSerializer can see request.user)
        rep['course'] = CourseSerializer(instance.course, context=self.context).data
        return rep



class DailyTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyTask
        fields = '__all__'
        read_only_fields = ['assigned_on']



class TaskSubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.username', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    task_question = serializers.CharField(source='task.question', read_only=True)
    course_title = serializers.CharField(source='task.course.title', read_only=True)  # ✅ new

    class Meta:
        model = TaskSubmission
        fields = "__all__"
        read_only_fields = ["student", "submitted_on"]



class OfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = '__all__'


class FeedbackSerializer(serializers.ModelSerializer):
    student = serializers.CharField(source="student.username", read_only=True)

    class Meta:
        model = Feedback
        fields = ["id", "rating", "comment", "created_at", "course", "student"]
        read_only_fields = ["created_at"]




class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['created_at']


class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = '__all__'
        read_only_fields = ['issue_date']


# serializers.py

class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = "__all__"

class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = "__all__"

class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    course = serializers.PrimaryKeyRelatedField(read_only=True)  # ✅ this line fixes the issue

    class Meta:
        model = Quiz
        fields = "__all__"


class StudentQuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentQuizAttempt
        fields = "__all__"




class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields =  '__all__'
        read_only_fields = ["id", "created_at", "updated_at"]


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'order', 'course', 'lessons']
        read_only_fields = ['course']




class LiveSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LiveSession
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")

        # ✅ Only instructors get start_url
        if not request or not request.user.is_authenticated or request.user != instance.instructor:
            data.pop("start_url", None)
        return data




class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = '__all__'
        read_only_fields = ['created_at', 'response']



class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class LessonCompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonCompletion
        fields = "__all__"
        read_only_fields = ["student", "completed_at"]



class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "sender", "content", "timestamp"]


class ChatRoomSerializer(serializers.ModelSerializer):
    course = serializers.PrimaryKeyRelatedField(read_only=True)
    student = UserSerializer(read_only=True)
    instructor = UserSerializer(read_only=True)
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatRoom
        fields = ["id", "course", "student", "instructor", "messages", "created_at"]

