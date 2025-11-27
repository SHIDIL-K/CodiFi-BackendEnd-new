# --- (imports stay exactly the same) ---

# Keep all imports as they are
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.core.mail import send_mail
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db.models import Sum
from django.db import transaction
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import filters
from rest_framework.decorators import action
from django.db.models import Count, Q, Avg
from rest_framework import status
import razorpay
from django.conf import settings
from django.shortcuts import get_object_or_404
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from django.shortcuts import redirect
from django.http import JsonResponse
import os
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from django.core.exceptions import PermissionDenied
import requests
from .utils.zoom import get_zoom_access_token
from datetime import timedelta
from django.utils import timezone
from groq import Groq
from django.contrib.auth import get_user_model
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags
from datetime import datetime


from .models import (
    ChatRoom, LessonCompletion, Notification, Question, StudentQuizAttempt, User, Course, Enrollment, DailyTask, TaskSubmission, Offer, Feedback, Payment, Profile,
    Module, Lesson, Quiz,  LiveSession,Message,
)
from .serializers import (
    ChatRoomSerializer, MessageSerializer, NotificationSerializer, OptionSerializer, QuestionSerializer, RegisterSerializer, StudentQuizAttemptSerializer, UserSerializer, CourseSerializer, EnrollmentSerializer,
    DailyTaskSerializer, TaskSubmissionSerializer, FeedbackSerializer,
    PaymentSerializer, ModuleSerializer, LessonSerializer,
    QuizSerializer,  LiveSessionSerializer,
    ProfileSerializer
)
from .permissions import IsInstructor, IsAdmin
from rest_framework.parsers import MultiPartParser, FormParser

from myapp import serializers


# =======================================
# 1) JWT Login, Registration, Profile
# =======================================

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.role == 'instructor' and not self.user.is_approved:
            raise AuthenticationFailed("Your instructor account is pending admin approval.")
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        if user.role == 'instructor':
            send_mail(
                subject="Instructor Approval Pending",
                message=f"New instructor '{user.username}' has registered and is awaiting approval.",
                from_email="noreply@codifi.com",
                recipient_list=["admin@codifi.com"],
                fail_silently=True,
            )


from .tasks import send_student_welcome_email

class StudentRegisterView(RegisterView):

    def perform_create(self, serializer):
        raw_password = self.request.data.get('password')
        user = serializer.save(role='student')

        # 🚀 Send email asynchronously using Celery
        send_student_welcome_email.delay(
            username=user.username,
            email=user.email,
            raw_password=raw_password,
        )



class InstructorRegisterView(RegisterView):
    def perform_create(self, serializer):
        serializer.save(role='instructor')


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = ProfileSerializer(profile, context={"request": request})
        return Response(serializer.data)

    def put(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        user = request.user

        profile.bio = request.data.get("bio", profile.bio)
        profile.phone = request.data.get("phone", profile.phone)
        profile.qualification = request.data.get("qualification", profile.qualification)
        profile.save()

        if "profile_picture" in request.FILES:
            user.profile_picture = request.FILES["profile_picture"]
        user.save()

        serializer = ProfileSerializer(profile, context={"request": request})
        return Response(serializer.data)


# =======================================
# 2) Courses (public + instructor)
# =======================================

class CourseListView(generics.ListAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.AllowAny]

    def get_serializer_context(self):
        return {"request": self.request}



# ❌ Removed AdminCourseCreateView & CourseRetrieveUpdateDeleteView
# Django superuser will manage Course creation/update via admin panel.


# =======================================
# 3) Enrollment + Payments
# =======================================

class EnrollmentCreateView(generics.CreateAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        try:
            course_id = request.data.get("course_id")
            if not course_id:
                return Response({"error": "course_id is required"}, status=status.HTTP_400_BAD_REQUEST)

            course = get_object_or_404(Course, id=course_id)
            student = request.user

            # prevent duplicate enrollments
            enrollment, created = Enrollment.objects.get_or_create(student=student, course=course)
            if not created:
                return Response({"message": "Already enrolled in this course"}, status=status.HTTP_200_OK)

            serializer = self.get_serializer(enrollment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PaymentCreateView(generics.CreateAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer):
        student = self.request.user
        course = serializer.validated_data['course']
        amount = serializer.validated_data['amount']

        # Apply offer if exists
        active_offer = Offer.objects.filter(is_active=True).order_by('-created_at').first()
        if active_offer and active_offer.discount_percent > 0:
            discount = (active_offer.discount_percent / 100) * float(amount)
            amount = float(amount) - discount

        payment = serializer.save(student=student, amount=amount)
        if payment.status == 'success':
            Enrollment.objects.get_or_create(student=student, course=course)


# views.py
class EnrollmentListView(generics.ListAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Enrollment.objects.filter(student=self.request.user)

    def get_serializer_context(self):
        # ✅ ensures request gets into EnrollmentSerializer → CourseSerializer
        return {"request": self.request}



# =======================================
# 4) Daily Tasks, Quizzes, Lessons, Feedback
# =======================================

class DailyTaskListView(generics.ListAPIView):
    serializer_class = DailyTaskSerializer
    queryset = DailyTask.objects.all()

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Ensure we always return a simple list, not paginated dict
        if isinstance(response.data, dict) and "results" in response.data:
            return Response(response.data["results"])
        return response



class TaskSubmissionCreateView(generics.CreateAPIView):
    queryset = TaskSubmission.objects.all()
    serializer_class = TaskSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Automatically attach the logged-in user as the student
        serializer.save(student=self.request.user)



class QuizListCreateView(generics.ListCreateAPIView):
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Quiz.objects.filter(course_id=self.kwargs["course_id"])

    def perform_create(self, serializer):
        serializer.save(course_id=self.kwargs["course_id"])


class QuestionCreateView(generics.CreateAPIView):
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated]


class OptionCreateView(generics.CreateAPIView):
    serializer_class = OptionSerializer
    permission_classes = [permissions.IsAuthenticated]


class StudentAttemptView(generics.CreateAPIView):
    serializer_class = StudentQuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        question_id = request.data.get("question")
        selected_option = request.data.get("selected_option")
        quiz_id = request.data.get("quiz")

        if not question_id or not selected_option or not quiz_id:
            return Response(
                {"error": "quiz, question, and selected_option are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            question = Question.objects.get(id=question_id)
        except Question.DoesNotExist:
            return Response(
                {"error": f"Question {question_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        is_correct = (question.correct_option == selected_option)

        attempt = StudentQuizAttempt.objects.create(
            student=request.user,
            quiz_id=quiz_id,
            question=question,
            selected_option=selected_option,
            is_correct=is_correct,
        )

        serializer = StudentQuizAttemptSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class QuizUpdateView(generics.UpdateAPIView):
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]


class QuizDeleteView(generics.DestroyAPIView):
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

class QuestionUpdateView(generics.UpdateAPIView):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated]

class QuestionDeleteView(generics.DestroyAPIView):
    queryset = Question.objects.all()
    permission_classes = [permissions.IsAuthenticated]



class InstructorDailyTaskCreateView(generics.CreateAPIView):
    serializer_class = DailyTaskSerializer
    permission_classes = [IsInstructor]

    def perform_create(self, serializer):
        course_id = self.request.data.get("course")
        course = Course.objects.filter(id=course_id, instructor=self.request.user).first()

        if not course:
            raise PermissionError("You are not assigned to this course.")

        # Save the new task
        task = serializer.save(course=course)

        # 🔔 Notify enrolled students
        for student in course.enrolled_students:
            Notification.objects.create(
                recipient=student,
                actor=self.request.user,
                title=f"New Daily Task: {task.title}",
                message=f"A new task has been added to {course.title}. Check it out!",
                notif_type='task',
                url=f"/student/courses/{course.id}/tasks"  # frontend route for the student
            )



class DailyTaskUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = DailyTask.objects.all()
    serializer_class = DailyTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Instructors can only edit/delete their own course's tasks
        if user.role == "instructor":
            return DailyTask.objects.filter(course__instructor=user)
        return DailyTask.objects.none()


class InstructorLiveSessionCreateView(generics.CreateAPIView):
    serializer_class = LiveSessionSerializer
    permission_classes = [IsInstructor]

    def perform_create(self, serializer):
        course_id = self.request.data.get("course")
        course = Course.objects.filter(id=course_id, instructor=self.request.user).first()
        if not course:
            raise PermissionError("You are not assigned to this course.")
        serializer.save(course=course, instructor=self.request.user)




from rest_framework.exceptions import ValidationError

from rest_framework.exceptions import ValidationError

class FeedbackCreateView(generics.CreateAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        course_id = self.request.data.get("course")

        if not course_id:
            raise ValidationError({"course": "Course ID is required."})

        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            raise ValidationError({"course": "Invalid course ID."})

        # Must be enrolled
        if not Enrollment.objects.filter(student=user, course=course).exists():
            raise ValidationError({"detail": "You must be enrolled in this course to leave a review."})

        # One review per student
        if Feedback.objects.filter(student=user, course=course).exists():
            raise ValidationError({"detail": "You have already reviewed this course."})

        serializer.save(student=user, course=course)



class FeedbackUpdateView(generics.UpdateAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Feedback.objects.all()

    def get_object(self):
        feedback = super().get_object()
        if feedback.student != self.request.user:
            raise PermissionDenied("You can edit only your own review.")
        return feedback

    def patch(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().patch(request, *args, **kwargs)


    
class FeedbackDeleteView(generics.DestroyAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Feedback.objects.all()

    def get_object(self):
        feedback = super().get_object()
        if feedback.student != self.request.user:
            raise PermissionDenied("You can delete only your own review.")
        return feedback


class CourseFeedbackListView(generics.ListAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        course_id = self.kwargs.get("course_id")
        return Feedback.objects.filter(course_id=course_id).order_by('-created_at')



# =======================================
# 5) Course Detail (for frontend)
# =======================================

class CourseDetailView(generics.RetrieveAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.AllowAny]

    def retrieve(self, request, *args, **kwargs):
        course = self.get_object()

        modules = Module.objects.filter(course=course).order_by("order")
        feedbacks = Feedback.objects.filter(course=course)

        course_data = CourseSerializer(course, context={'request': request}).data
        module_data = ModuleSerializer(modules, many=True, context={'request': request}).data
        feedbacks_data = FeedbackSerializer(feedbacks, many=True, context={'request': request}).data

        return Response({
            "course": course_data,
            "modules": module_data,   # ⬅️ RETURN MODULES
            "reviews": feedbacks_data,
        })



# =======================================
# 6) Public & Instructor Utilities
# =======================================

class CourseSearchView(generics.ListAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'instructor__username']
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']


class InstructorListView(generics.ListAPIView):
    queryset = User.objects.filter(role='instructor', is_approved=True)
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

class InstructorEnrollmentListView(generics.ListAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        return Enrollment.objects.filter(course__instructor=self.request.user)

class InstructorCourseListView(generics.ListAPIView):
    serializer_class = CourseSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        # Only show courses created by admin AND assigned to this instructor
        return Course.objects.filter(instructor=self.request.user, created_by_admin=True)


# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZOR_KEY_ID, settings.RAZOR_KEY_SECRET))

class CreateRazorpayOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            course_id = request.data.get("course_id")
            if not course_id:
                return Response({"error": "Course ID is required"}, status=400)

            course = Course.objects.get(id=course_id)
            student = request.user

            # ✅ Use consistent offer logic (matching frontend CourseSerializer)
            final_price = course.get_final_price(user=request.user)

            if not final_price:
                return Response({"error": "Price calculation failed."}, status=400)

            amount = int(float(final_price) * 100)    # Razorpay uses paise

            print("✔ Final price for payment:", final_price)
            print("✔ Razorpay order amount:", amount)

            # ✅ Create Razorpay order
            order = razorpay_client.order.create({
                "amount": amount,
                "currency": "INR",
                "payment_capture": "1",
            })

            # ✅ Save payment record locally
            Payment.objects.create(
                student=student,
                course=course,
                amount=final_price,
                order_id=order["id"],
                status="pending"
            )

            # ✅ Return order info to frontend
            return Response({
                "order_id": order["id"],
                "amount": amount,
                "currency": "INR",
                "key": settings.RAZOR_KEY_ID,
                "course_title": course.title,
                "final_price": final_price
            }, status=200)

        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=404)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=400)




# views.py
from myapp.tasks import send_payment_success_email


class VerifyRazorpayPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            data = request.data
            razorpay_order_id = data.get("razorpay_order_id")
            razorpay_payment_id = data.get("razorpay_payment_id")
            razorpay_signature = data.get("razorpay_signature")

            if not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
                return Response({"error": "Missing required payment details"}, status=status.HTTP_400_BAD_REQUEST)

            # ✅ Verify signature
            params_dict = {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
            razorpay_client.utility.verify_payment_signature(params_dict)

            # ✅ Find the payment record
            payment = get_object_or_404(Payment, order_id=razorpay_order_id)
            payment.payment_id = razorpay_payment_id
            payment.status = "success"
            payment.save()

            # ✅ Enroll the student automatically
            student = request.user
            course = payment.course
            enrollment, created = Enrollment.objects.get_or_create(student=student, course=course)

            # Always calculate/refresh expiry
            enrollment.expires_on = timezone.now() + timedelta(days=course.course_duration_months * 30)            
            enrollment.save()

            
            payment_date = timezone.now().strftime("%B %d, %Y")

            # 📧 Send Email via Celery (ASYNC — FAST)
            send_payment_success_email.delay(
                username=student.username,
                email=student.email,
                course_title=course.title,
                transaction_id=payment.transaction_id,
                amount=str(payment.amount),
                payment_date=payment_date,
            )

            # ✅ Return confirmation
            return Response({
                "message": "Payment verified, student enrolled, and confirmation email sent successfully.",
                "course_id": course.id,
                "enrolled": True,
            }, status=status.HTTP_200_OK)

        except razorpay.errors.SignatureVerificationError:
            return Response({"error": "Payment signature verification failed"}, status=status.HTTP_400_BAD_REQUEST)
        except Payment.DoesNotExist:
            return Response({"error": "Payment record not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



# In views.py
class TaskSubmissionListView(generics.ListAPIView):
    """
    List all student task submissions for the instructor's course.
    """
    serializer_class = TaskSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        course_id = self.kwargs.get("course_id")

        # Only allow instructors to view submissions for their courses
        if user.role == "instructor":
            return TaskSubmission.objects.filter(
                task__course__id=course_id,
                task__course__instructor=user
            ).select_related("student", "task", "task__course")

        return TaskSubmission.objects.none()

class TaskSubmissionReviewView(generics.UpdateAPIView):
    """
    Approve or reject a submission with feedback.
    """
    serializer_class = TaskSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = TaskSubmission.objects.all()

    def update(self, request, *args, **kwargs):
        submission = self.get_object()
        user = request.user

        # Ensure instructor owns this course
        if user != submission.task.course.instructor:
            return Response({"detail": "Not authorized"}, status=403)

        new_status = request.data.get("status")
        feedback = request.data.get("feedback", "")

        if new_status not in ["approved", "rejected"]:
            return Response({"detail": "Invalid status"}, status=400)

        submission.status = new_status
        submission.feedback = feedback
        submission.save()
        serializer = self.get_serializer(submission)
        return Response(serializer.data)


class StudentTaskSubmissionListView(generics.ListAPIView):
    serializer_class = TaskSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TaskSubmission.objects.filter(student=self.request.user)
    



class StudentCourseProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, course_id):
        user = request.user

        # ✅ Ensure user is enrolled
        enrollment = Enrollment.objects.filter(student=user, course_id=course_id).first()
        if not enrollment:
            return Response({"detail": "Not enrolled in this course"}, status=403)

        # ✅ Count total lessons inside ALL modules of this course
        total_lessons = Lesson.objects.filter(module__course_id=course_id).count()

        # ✅ Count completed lessons from LessonCompletion model
        completed_lessons = LessonCompletion.objects.filter(
            student=user,
            lesson__module__course_id=course_id
        ).count()

        # ✅ Daily tasks progress
        total_tasks = DailyTask.objects.filter(course_id=course_id).count()
        completed_tasks = TaskSubmission.objects.filter(
            student=user, task__course_id=course_id, status="approved"
        ).count()
        rejected_tasks = TaskSubmission.objects.filter(
            student=user, task__course_id=course_id, status="rejected"
        ).count()
        pending_tasks = total_tasks - (completed_tasks + rejected_tasks)

        # ✅ % Progress calculations
        lesson_progress = (completed_lessons / total_lessons * 100) if total_lessons else 0
        task_progress = (completed_tasks / total_tasks * 100) if total_tasks else 0

        # ✅ Overall course progress
        course_progress = round((lesson_progress + task_progress) / 2, 2)

        # ✅ Update enrollment progress
        enrollment.progress = course_progress
        enrollment.save(update_fields=["progress"])

        if enrollment.expires_on and enrollment.expires_on < timezone.now():
            return Response({"expired": True, "message": "Your course access has expired."}, status=403)

        return Response({
            "course_progress": course_progress,
            "lesson_progress": round(lesson_progress, 2),
            "task_progress": round(task_progress, 2),
            "completed_lessons": completed_lessons,
            "total_lessons": total_lessons,
            "completed_tasks": completed_tasks,
            "rejected_tasks": rejected_tasks,
            "pending_tasks": max(pending_tasks, 0),
            "total_tasks": total_tasks,
            "expires_on": enrollment.expires_on.isoformat() if enrollment.expires_on else None,
        })




#Lesson

class YouTubeSearchView(APIView):
    """
    Proxy search to YouTube Data API using server-side key.
    GET param: q (query), optional maxResults
    """
    permission_classes = [permissions.IsAuthenticated]  # restrict to logged-in instructors if you want
    def get(self, request):
        q = request.GET.get("q", "")
        if not q:
            return Response({"error":"q param required"}, status=status.HTTP_400_BAD_REQUEST)
        max_results = request.GET.get("maxResults", "6")
        api_key = getattr(settings, "YOUTUBE_API_KEY", None)
        if not api_key:
            return Response({"error":"YouTube API key not configured on server."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "type": "video",
            "q": q,
            "maxResults": max_results,
            "key": api_key,
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return Response({"error":"YouTube API error", "detail": r.text}, status=r.status_code)
        data = r.json()
        # simplify the response: return id, title, thumbnails, description
        items = []
        for it in data.get("items", []):
            vid = it.get("id", {}).get("videoId")
            sn = it.get("snippet", {})
            items.append({
                "videoId": vid,
                "title": sn.get("title"),
                "description": sn.get("description"),
                "channelTitle": sn.get("channelTitle"),
                "thumbnails": sn.get("thumbnails", {}),
            })
        return Response({"items": items})

class InstructorLessonCreateView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        module_id = request.data.get("module")
        if not module_id:
            return Response({"error": "Module ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        module = get_object_or_404(Module, id=module_id, course__instructor=request.user)
        serializer = LessonSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(module=module)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CourseLessonsListView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({"error":"Course not found"}, status=status.HTTP_404_NOT_FOUND)

        # collect lessons across modules
        lessons = Lesson.objects.filter(module__course=course).order_by('order', 'created_at')
        serializer = LessonSerializer(lessons, many=True, context={"request": request})
        return Response({"lessons": serializer.data})

class CourseModulesWithLessonsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=404)

        modules = Module.objects.filter(course=course).order_by('order')
        serializer = ModuleSerializer(modules, many=True, context={"request": request})
        return Response({"modules": serializer.data})


# add below CourseLessonsListView in views.py
class InstructorModuleListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, course_id):
        """List all modules for a course (instructor view)"""
        course = get_object_or_404(Course, id=course_id, instructor=request.user)
        modules = Module.objects.filter(course=course)
        serializer = ModuleSerializer(modules, many=True)
        return Response(serializer.data)

    def post(self, request, course_id):
        """Create a new module under a course"""
        course = get_object_or_404(Course, id=course_id, instructor=request.user)
        serializer = ModuleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(course=course)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LessonDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, lesson_id):
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=404)
        # Expiry check
        user = request.user
        if user.is_authenticated and user.role == 'student':
            enrollment = Enrollment.objects.filter(student=user, course=lesson.module.course).first()
            if enrollment and enrollment.expires_on and enrollment.expires_on < timezone.now():
                return Response({"expired": True, "message": "Your course access has expired."}, status=403)

        serializer = LessonSerializer(lesson, context={"request": request})
        return Response(serializer.data)



class YouTubeVideoDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, video_id):
        try:
            api_key = settings.YOUTUBE_API_KEY
            if not api_key:
                return Response({"error": "YouTube API key missing"}, status=500)

            url = (
                f"https://www.googleapis.com/youtube/v3/videos"
                f"?part=snippet,contentDetails,statistics&id={video_id}&key={api_key}"
            )
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # ✅ return the JSON from YouTube directly
            return Response(data, status=response.status_code)
        except requests.exceptions.RequestException as e:
            return Response({"error": str(e)}, status=500)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        

#Zoom 
class ZoomCreateMeetingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, course_id):
        topic = request.data.get("topic", "Live Session")
        start_time = request.data.get("start_time")
        duration = int(request.data.get("duration", 60))

        from .models import Course, LiveSession

        try:
            course = Course.objects.get(id=course_id, instructor=request.user)
        except Course.DoesNotExist:
            return Response({"error": "Course not found or not owned by instructor"}, status=404)

        try:
            # 🔐 Get access token from Zoom
            token_url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={settings.ZOOM_ACCOUNT_ID}"
            auth = (settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET)
            token_res = requests.post(token_url, auth=auth)
            token_res.raise_for_status()
            access_token = token_res.json()["access_token"]

            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

            # 🧩 Simplified payload (works for both free & paid)
            payload = {
                "topic": topic,
                "type": 2,  # Scheduled meeting
                "start_time": start_time,
                "duration": duration,
                "timezone": "Asia/Kolkata",
                "settings": {
                    "join_before_host": False,
                    "waiting_room": True,
                    "approval_type": 2,  # Auto-approval for registrants (or ignored on free)
                    "registration_type": 1,
                    "meeting_authentication": False,  # ❌ disable strict auth (needed for free accounts)
                    "host_video": True,
                    "participant_video": True,
                    "mute_upon_entry": True,
                    "allow_multiple_devices": True,
                },
            }

            # 📡 Create meeting via Zoom API
            res = requests.post("https://api.zoom.us/v2/users/me/meetings", headers=headers, json=payload)
            res.raise_for_status()
            zoom_data = res.json()

            # 🧾 Save meeting to database
            live = LiveSession.objects.create(
                course=course,
                instructor=request.user,
                topic=topic,
                start_time=start_time,
                duration=duration,
                join_url=zoom_data.get("join_url"),
                start_url=zoom_data.get("start_url"),
                zoom_meeting_id=str(zoom_data.get("id")),
            )

            serializer = LiveSessionSerializer(live, context={"request": request})
            return Response(serializer.data, status=201)

        except Exception as e:
            import traceback; traceback.print_exc()
            return Response({"error": f"Zoom meeting creation failed: {str(e)}"}, status=500)



class InstructorLiveSessionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, course_id):
        """
        Show only recent or live sessions for instructor.
        - upcoming: in next 24h
        - live: started but not finished
        - ended: finished within last 3 hours
        """
        now = timezone.now()
        UPCOMING_MINUTES = 24 * 60
        ENDED_WITHIN_MINUTES = 180  # 3 hours

        start_from = now - timedelta(minutes=ENDED_WITHIN_MINUTES)
        start_to = now + timedelta(minutes=UPCOMING_MINUTES)

        sessions = LiveSession.objects.filter(
            course_id=course_id, instructor=request.user,
            start_time__gte=start_from, start_time__lte=start_to
        ).order_by("-start_time")

        data = []
        for s in sessions:
            end_time = s.start_time + timedelta(minutes=s.duration)
            if end_time < now:
                status_label = "ended"
            elif s.start_time > now:
                status_label = "upcoming"
            else:
                status_label = "live"

            data.append({
                "id": s.id,
                "topic": s.topic,
                "start_time": s.start_time,
                "duration": s.duration,
                "status": status_label,
                "join_url": s.join_url,
                "start_url": s.start_url,
                "zoom_meeting_id": s.zoom_meeting_id,
            })

        return Response(data, status=200)

    def delete(self, request, course_id):
        """
        Allow instructor to delete a specific session by ?id= param.
        """
        session_id = request.query_params.get("id")
        if not session_id:
            return Response({"error": "Missing session id"}, status=400)

        try:
            session = LiveSession.objects.get(id=session_id, course_id=course_id, instructor=request.user)
            session.delete()
            return Response({"message": "Session deleted successfully"}, status=200)
        except LiveSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=404)
        
        
class CourseLiveSessionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, course_id):
        now = timezone.now()
        UPCOMING_WITHIN_MINUTES = 24 * 60   # upcoming in next 24 hours
        ENDED_WITHIN_MINUTES = 120          # ended within last 2 hours

        start_from = now - timedelta(minutes=ENDED_WITHIN_MINUTES)
        start_to = now + timedelta(minutes=UPCOMING_WITHIN_MINUTES)

        sessions = LiveSession.objects.filter(
            course_id=course_id,
            start_time__gte=start_from,
            start_time__lte=start_to
        ).order_by("start_time")

        data = []
        for s in sessions:
            end_time = s.start_time + timedelta(minutes=s.duration or 0)
            if end_time < now:
                status = "ended"
            elif s.start_time > now:
                status = "upcoming"
            else:
                status = "live"

            data.append({
                "id": s.id,
                "topic": s.topic,
                "start_time": s.start_time,
                "duration": s.duration,
                "status": status,
                "join_url": s.join_url,
                "zoom_meeting_id": s.zoom_meeting_id,
            })

        return Response(data)


class RegisterForLiveSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        from .models import LiveSession

        try:
            session = LiveSession.objects.get(id=session_id)
        except LiveSession.DoesNotExist:
            return Response({"error": "Live session not found"}, status=404)

        if request.user.role != "student":
            return Response({"error": "Only students can register"}, status=403)

        # ✅ Always return join_url directly (free accounts can't register users)
        if session.join_url:
            return Response(
                {
                    "join_url": session.join_url,
                    "message": "Direct join link provided (no instructor approval required)",
                },
                status=200,
            )

        # 🧩 Optional: fallback if no join_url exists
        return Response(
            {"error": "No Zoom join link available for this session"},
            status=400,
        )




# Chat Bot

# Initialize client once (you can move this to settings)
client = Groq(api_key=settings.GROQ_API_KEY)

class ChatBotAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # Only logged-in users can use it

    def post(self, request):
        user_message = request.data.get("message", "").strip()
        if not user_message:
            return Response({"response": "Please enter a message."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Call Groq API (LLama 3.3 70B)
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful AI tutor for an e-learning platform."},
                    {"role": "user", "content": user_message},
                ],
                model="llama-3.3-70b-versatile",
                stream=False,
                max_tokens=200,
            )

            chatbot_reply = chat_completion.choices[0].message.content.strip()
            return Response({"response": chatbot_reply}, status=200)

        except Exception as e:
            return Response({"response": f"Error: {str(e)}"}, status=500)
        

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    authentication_classes = [JWTAuthentication]  # ✅ explicit
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'All notifications marked as read'})
    



class MarkLessonCompletedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, lesson_id):
        user = request.user

        # ✅ Check lesson exists
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response({"detail": "Lesson not found"}, status=404)

        # ✅ Ensure student is enrolled & get the enrollment object first
        try:
            enrollment = Enrollment.objects.get(student=user, course=lesson.course)
        except Enrollment.DoesNotExist:
            return Response({"detail": "You are not enrolled in this course."}, status=403)

        # ✅ Check expiry AFTER enrollment is defined
        if enrollment.expires_on and enrollment.expires_on < timezone.now():
            return Response({"detail": "Course access expired"}, status=403)

        # ✅ Mark lesson as completed
        completion, created = LessonCompletion.objects.get_or_create(
            student=user,
            lesson=lesson
        )

        # ✅ Calculate progress
        total_lessons = Lesson.objects.filter(course=lesson.course).count()
        completed_lessons = LessonCompletion.objects.filter(
            student=user,
            lesson__course=lesson.course
        ).count()

        progress_percent = (completed_lessons / total_lessons) * 100

        # ✅ Update enrollment progress
        enrollment.progress = progress_percent
        enrollment.save()

        return Response({
            "completed": True,
            "created": created,
            "progress": progress_percent
        }, status=200)



class LessonCompletionStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lesson_id):
        user = request.user
        completed = LessonCompletion.objects.filter(student=user, lesson_id=lesson_id).exists()
        return Response({"completed": completed})


class InstructorDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != "instructor":
            return Response({"detail": "Not authorized"}, status=403)

        # ✅ Fetch courses assigned to instructor
        courses = Course.objects.filter(instructor=user)
        total_courses = courses.count()

        # ✅ Count total students across all allocated courses
        total_students = Enrollment.objects.filter(course__instructor=user).count()

        # ✅ Average rating across all instructor’s courses
        avg_rating = (
            Feedback.objects.filter(course__instructor=user).aggregate(Avg("rating"))["rating__avg"] or 0
        )

        # ✅ Feedback count (number of reviews)
        feedback_count = Feedback.objects.filter(course__instructor=user).count()

        # ✅ Course details
        course_data = [
            {
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "image": c.image.url if c.image else "",
                "enrolled_students": Enrollment.objects.filter(course=c).count(),
            }
            for c in courses
        ]

        return Response({
            "stats": {
                "totalCourses": total_courses,
                "totalStudents": total_students,
                "avgRating": avg_rating,
                "feedbackCount": feedback_count,
            },
            "courses": course_data,
        })
    


# 🔹 Chat between Instructor ↔ Student
User = get_user_model()

class GetOrCreateCourseChat(APIView):
    """
    Creates or retrieves a chatroom between a student and the instructor for a specific course.
    Handles both student and instructor requests.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)
        instructor = getattr(course, "instructor", None)

        if not instructor:
            return Response({"detail": "Course has no instructor."}, status=400)

        # 🔹 Determine the target student
        student_id = request.data.get("student_id")
        if user == instructor:
            # Instructor is starting the chat with a student
            if not student_id:
                return Response({"detail": "student_id is required for instructor"}, status=400)
            student = get_object_or_404(User, id=student_id)
        else:
            # Student is starting the chat
            student = user

        # 🔹 Get or create chatroom
        chatroom, created = ChatRoom.objects.get_or_create(
            course=course,
            student=student,
            instructor=instructor,
        )

        serializer = ChatRoomSerializer(chatroom)
        return Response(
            {"id": chatroom.id, "created": created, "message": "Chat room ready"},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ChatRoomDetailAPI(generics.RetrieveAPIView):
    queryset = ChatRoom.objects.all()
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]


class SendMessageAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, chatroom_id):
        chatroom = get_object_or_404(ChatRoom, id=chatroom_id)
        content = request.data.get("content", "").strip()

        if not content:
            return Response({"detail": "Empty message"}, status=400)

        message = Message.objects.create(chatroom=chatroom, sender=request.user, content=content)
        return Response(MessageSerializer(message).data, status=201)

from dateutil.parser import parse


class ChatRoomListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        rooms = ChatRoom.objects.filter(
            Q(instructor=user) | Q(student=user)
        ).distinct()

        response_data = []

        for room in rooms:
            last_msg = room.messages.order_by("-timestamp").first()

            # ✔ Count only unread messages sent by student
            unread_count = room.messages.filter(
                sender=room.student,
                is_read=False         # 👈 THIS FIXES THE ISSUE
            ).count()

            response_data.append({
                "chatroom_id": room.id,
                "course_title": room.course.title,
                "course_id": room.course.id,
                "student_id": room.student.id,
                "student_username": room.student.username,
                "last_message": last_msg.content if last_msg else "",
                "last_message_at": last_msg.timestamp.isoformat() if last_msg else None,
                "unread_count": unread_count,
            })

        # Sort: unread first, then latest messages
        response_data.sort(
            key=lambda x: (
                -(x["unread_count"] or 0),
                parse(x["last_message_at"]) if x["last_message_at"] else parse("1970-01-01T00:00:00Z")
            )
        )

        return Response(response_data)

class MarkMessagesReadAPI(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, chatroom_id):
        user = request.user
        chatroom = get_object_or_404(ChatRoom, id=chatroom_id)

        # Only instructor should mark messages as read
        if user != chatroom.instructor:
            return Response({"detail": "Only instructor can mark messages"}, status=403)

        # Mark unread student messages as read
        chatroom.messages.filter(
            sender=chatroom.student,
            is_read=False
        ).update(is_read=True)

        return Response({"status": "messages marked as read"})
