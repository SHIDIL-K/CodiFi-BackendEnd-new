from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    # Auth & Profile
    ChatRoomDetailAPI, ChatRoomListAPI, FeedbackDeleteView, GetOrCreateCourseChat, 
    InstructorDashboardView, LessonCompletionStatusView, MarkLessonCompletedView, MarkMessagesReadAPI, 
    NotificationViewSet, QuestionDeleteView, QuestionUpdateView, QuizDeleteView, 
    QuizUpdateView, RegisterView, SendMessageAPI, StudentRegisterView, InstructorRegisterView,
    ProfileView, CustomTokenObtainPairView,

    # Course-related
    CourseListView, CourseDetailView, CourseSearchView,
    StudentTaskSubmissionListView,StudentCourseProgressView,LessonDetailView,

    # Enrollment & Payment
    EnrollmentCreateView, PaymentCreateView,CreateRazorpayOrderView,VerifyRazorpayPaymentView,EnrollmentListView,

    # Feedback
    FeedbackCreateView,CourseFeedbackListView,FeedbackUpdateView,


    # Instructor-related
    InstructorListView, InstructorCourseListView, InstructorEnrollmentListView,
    InstructorDailyTaskCreateView, TaskSubmissionReviewView, InstructorLiveSessionCreateView,
    TaskSubmissionListView,DailyTaskUpdateDeleteView,YouTubeSearchView,InstructorLessonCreateView,CourseLessonsListView,
    InstructorModuleListCreateView,CourseModulesWithLessonsView,YouTubeVideoDetailView,ZoomCreateMeetingView,InstructorLiveSessionListView,
    


    # Tasks & Quizzes
    DailyTaskListView, TaskSubmissionCreateView,CourseLiveSessionsView,RegisterForLiveSessionView,
    QuizListCreateView, QuestionCreateView, OptionCreateView, StudentAttemptView,


    # Chatbot
    ChatBotAPIView,
    
)

from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notifications')

urlpatterns = [
    # Django Admin (superuser handles all admin tasks here)
    path('api/', include(router.urls)),

    # Authentication & Registration
    path('api/register/', RegisterView.as_view(), name='register'),
    path('api/register/student/', StudentRegisterView.as_view(), name='register-student'),
    path('api/register/instructor/', InstructorRegisterView.as_view(), name='register-instructor'),
    path('api/profile/', ProfileView.as_view(), name='profile'),

    # JWT Tokens
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair_custom'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Courses (public)
    path('api/courses/', CourseListView.as_view(), name='course-list'),
    path('api/courses/search/', CourseSearchView.as_view(), name='course-search'),
    path('api/courses/<int:pk>/detail/', CourseDetailView.as_view(), name='course-detail'),
    # path('api/courses/<int:pk>/lessons/', CourseLessonsView.as_view(), name='course-lessons'),
    path("api/courses/<int:course_id>/progress/", StudentCourseProgressView.as_view(), name="student-course-progress"),

    
    #Chat Section
    path("api/courses/<int:course_id>/chat/", GetOrCreateCourseChat.as_view(), name="get-or-create-chat"),
    path("api/chat/<int:pk>/", ChatRoomDetailAPI.as_view(), name="chatroom-detail"),
    path("api/chat/<int:chatroom_id>/send/", SendMessageAPI.as_view(), name="chatroom-send"),
    path("api/chat/rooms/", ChatRoomListAPI.as_view(), name="chatroom-list"),
    path("api/instructor/conversations/", ChatRoomListAPI.as_view(), name="instructor-conversations"),
    path("api/chat/<int:chatroom_id>/mark-read/", MarkMessagesReadAPI.as_view()),


    # Enrollment & Payments
    path("api/enrollments/", EnrollmentListView.as_view(), name="enrollment-list"),
    path("api/enrollments/create/", EnrollmentCreateView.as_view(), name="enroll-course"),
    path('api/payments/', PaymentCreateView.as_view(), name='payment-create'),


    # Razorpay Integration
    path("api/razorpay/create-order/", CreateRazorpayOrderView.as_view(), name="create_order"),
    path("api/razorpay/verify-payment/", VerifyRazorpayPaymentView.as_view(), name="verify_payment"),


    # Feedback
    path('api/courses/<int:course_id>/reviews/', CourseFeedbackListView.as_view()),
    path('api/reviews/create/', FeedbackCreateView.as_view()),
    path('api/reviews/<int:pk>/update/', FeedbackUpdateView.as_view()),
    path('api/reviews/<int:pk>/delete/', FeedbackDeleteView.as_view()),



    # Instructor related
    path('api/instructors/', InstructorListView.as_view(), name='instructor-list'),
    path('api/instructor/courses/', InstructorCourseListView.as_view(), name='instructor-courses'),
    path('api/instructor/enrollments/', InstructorEnrollmentListView.as_view(), name='instructor-enrollments'),
    path('api/instructor/tasks/create/', InstructorDailyTaskCreateView.as_view(), name='instructor-task-create'),
    path('api/daily-tasks/<int:pk>/', DailyTaskUpdateDeleteView.as_view(), name='daily-task-update-delete'),
    # GET - List all submissions for instructor
    path("api/instructor/courses/<int:course_id>/submissions/",TaskSubmissionListView.as_view(),name="task-submission-list"),
    # PUT/PATCH - Review (approve/reject/update feedback) a specific submission
    path("api/instructor/submissions/<int:pk>/review/", TaskSubmissionReviewView.as_view(), name='task-submission-review'),
    path('api/instructor/live/create/', InstructorLiveSessionCreateView.as_view(), name='instructor-live-create'),
    # Youtub+Lesson
    path("api/youtube/search/", YouTubeSearchView.as_view(), name="youtube-search"),
    path("api/youtube/video/<str:video_id>/", YouTubeVideoDetailView.as_view(), name="youtube-video-detail"),
    path("api/instructor/lessons/create/", InstructorLessonCreateView.as_view(), name="instructor-lesson-create"),
    path("api/courses/<int:course_id>/lessons/", CourseLessonsListView.as_view(), name="course-lessons"),
    path("api/instructor/courses/<int:course_id>/modules/", InstructorModuleListCreateView.as_view(), name="instructor-modules"),
    path("api/courses/<int:course_id>/modules-with-lessons/", CourseModulesWithLessonsView.as_view()),
    # ZOOM
    path("api/instructor/courses/<int:course_id>/zoom/create/", ZoomCreateMeetingView.as_view(), name="zoom-create-meeting"),
    path("api/instructor/courses/<int:course_id>/live-sessions/", InstructorLiveSessionListView.as_view(), name="zoom-list-meetings"),
    path("api/instructor-dashboard/", InstructorDashboardView.as_view(), name="instructor-dashboard"),


    # Daily Tasks
    path('api/tasks/', DailyTaskListView.as_view()),
    path('api/tasks/submit/', TaskSubmissionCreateView.as_view(), name='task-submit'),
    path('api/student/submissions/', StudentTaskSubmissionListView.as_view()),

    #Lessons
    path("api/lessons/<int:lesson_id>/", LessonDetailView.as_view(), name="lesson-detail"),
    path("api/lessons/<int:lesson_id>/complete/", MarkLessonCompletedView.as_view()),
    path("api/lessons/<int:lesson_id>/complete-status/", LessonCompletionStatusView.as_view()),



    # Zoom
    path("api/courses/<int:course_id>/live-sessions/", CourseLiveSessionsView.as_view()),
    path("api/live-sessions/<int:session_id>/register/", RegisterForLiveSessionView.as_view(), name="live-session-register"),



    # Quizzes
    path("api/courses/<int:course_id>/quizzes/", QuizListCreateView.as_view()),
    path("api/questions/create/", QuestionCreateView.as_view()),
    path("api/options/create/", OptionCreateView.as_view()),
    path("api/attempts/create/", StudentAttemptView.as_view()),
    path("api/quizzes/<int:pk>/update/", QuizUpdateView.as_view(), name="quiz-update"),
    path("api/quizzes/<int:pk>/delete/", QuizDeleteView.as_view(), name="quiz-delete"),
    path("api/questions/<int:pk>/update/", QuestionUpdateView.as_view(), name="question-update"),
    path("api/questions/<int:pk>/delete/", QuestionDeleteView.as_view(), name="question-delete"),


    # Chatbot
    path("api/chatbot/", ChatBotAPIView.as_view(), name="chatbot"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
