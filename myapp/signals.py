from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.conf import settings
from .models import DailyTask, LiveSession, Notification, User, Course


@receiver(post_save, sender=User)
def send_instructor_approval_email(sender, instance, created, **kwargs):
    """
    Sends an email when an instructor is approved by the superuser (is_approved=True).
    """
    # Only act on instructors
    if instance.role != "instructor":
        return

    # Skip new instructor creation (only trigger on approval)
    if created:
        return

    # Check if they were just approved
    if instance.is_approved:
        subject = "Welcome to CodiFi — Your Instructor Account is Approved 🎉"
        recipient_list = [instance.email]

        html_content = f"""
        <html>
        <body style="font-family: 'Inter', 'Segoe UI', sans-serif; background-color: #f8fafc; padding: 40px; margin: 0;">
            <div style="max-width: 650px; margin: auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 6px 18px rgba(0,0,0,0.08);">
                
                <!-- Header -->
                <div style="background: linear-gradient(90deg, #2563eb, #9333ea); padding: 24px 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: #9333ea; background: linear-gradient(90deg, #ffffff, #f9fafb); -webkit-background-clip: text;">
                        CodiFi Instructor Portal 💼
                    </h1>
                </div>

                <!-- Body -->
                <div style="padding: 35px 40px;">
                    <p style="font-size: 17px; color: #111827;">Hi <strong>{instance.username}</strong>,</p>

                    <p style="font-size: 15px; color: #374151; line-height: 1.7;">
                        Congratulations! 🎉<br>
                        Your instructor profile has been <strong style="color:#2563eb;">approved</strong> by the CodiFi admin team.
                        You can now log in to <strong style="color: #9333ea;">CodiFi</strong>.
                    </p>
                    <p style="font-size: 15px; color: #374151; line-height: 1.7;">
                        The admin team will soon allocate you to a course. When it is done we wiil notify you through the Email.
                    </p>



                    <div style="margin: 25px 0; padding: 18px 22px; background-color: #f0f5ff; border-left: 5px solid #6366f1; border-radius: 10px;">
                        <p style="margin: 0; font-size: 15px; color: #1e3a8a;">
                            <strong>👤 Username:</strong> {instance.username}<br>
                            <strong>📧 Email:</strong> {instance.email}
                        </p>
                    </div>

                    <p style="font-size: 15px; color: #374151; line-height: 1.7;">
                        You can log in to your instructor dashboard using the button below:
                    </p>

                    <p style="text-align: center; margin: 32px 0;">
                        <a href="http://localhost:5173/login"
                           style="background: linear-gradient(90deg, #2563eb, #9333ea);
                                  color: white; text-decoration: none;
                                  padding: 14px 28px;
                                  border-radius: 8px;
                                  font-weight: 600;
                                  letter-spacing: 0.3px;
                                  transition: opacity 0.2s;">
                            🎓 Go to CodiFi Dashboard
                        </a>
                    </p>

                    <p style="font-size: 14px; color: #6b7280;">
                        If you didn’t apply for an instructor account, please ignore this message.
                    </p>

                    <p style="margin-top: 25px; font-size: 15px; color: #111827;">
                        Welcome aboard,<br>
                        <strong style="color: #9333ea;">The CodiFi Team 💻</strong>
                    </p>
                </div>

                <!-- Footer -->
                <div style="background-color: #f9fafb; padding: 18px; text-align: center;">
                    <p style="font-size: 13px; color: #9ca3af; margin: 0;">
                        © 2025 <strong style="color: #2563eb;">CodiFi</strong>. All rights reserved.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = strip_tags(html_content)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)



@receiver(post_save, sender=Course)
def send_instructor_course_assignment_email(sender, instance, created, **kwargs):
    """
    Sends an email when an instructor is assigned to a course by the admin.
    """
    if not instance.instructor:
        return  # No instructor assigned yet

    subject = "You’ve Been Assigned a New Course — CodiFi 🎓"
    recipient_list = [instance.instructor.email]

    html_content = f"""
    <html>
    <body style="font-family: 'Inter', 'Segoe UI', sans-serif; background-color: #f8fafc; padding: 40px; margin: 0;">
        <div style="max-width: 650px; margin: auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 6px 18px rgba(0,0,0,0.08);">
            
            <!-- Header -->
            <div style="background: linear-gradient(90deg, #2563eb, #9333ea); padding: 24px 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: #9333ea; background: linear-gradient(90deg, #ffffff, #f9fafb); -webkit-background-clip: text;">
                    CodiFi Instructor Portal 💼
                </h1>
            </div>

            <!-- Body -->
            <div style="padding: 35px 40px;">
                <p style="font-size: 17px; color: #111827;">Hi <strong>{instance.instructor.username}</strong>,</p>

                <p style="font-size: 15px; color: #374151; line-height: 1.7;">
                    Great news! You’ve just been assigned to a new course on <strong style="color: #9333ea;">CodiFi</strong>.
                </p>

                <div style="margin: 25px 0; padding: 18px 22px; background-color: #f0f5ff; border-left: 5px solid #6366f1; border-radius: 10px;">
                    <p style="margin: 0; font-size: 15px; color: #1e3a8a;">
                        <strong>📘 Course Title:</strong> {instance.title}<br>
                        <strong>🗂 Description:</strong> {instance.description[:150]}...<br>
                        <strong>📅 Created On:</strong> {instance.created_at.strftime('%B %d, %Y')}
                    </p>
                </div>

                <p style="font-size: 15px; color: #374151; line-height: 1.7;">
                    You can now log in to your dashboard to manage this course, upload materials, and interact with your students.
                </p>

                <p style="text-align: center; margin: 32px 0;">
                    <a href="http://localhost:5173/login"
                       style="background: linear-gradient(90deg, #2563eb, #9333ea);
                              color: white; text-decoration: none;
                              padding: 14px 28px;
                              border-radius: 8px;
                              font-weight: 600;
                              letter-spacing: 0.3px;
                              transition: opacity 0.2s;">
                        🚀 Go to Instructor Dashboard
                    </a>
                </p>

                <p style="font-size: 15px; color: #111827;">
                    Cheers,<br>
                    <strong style="color: #9333ea;">The CodiFi Team 💻</strong>
                </p>
            </div>

            <!-- Footer -->
            <div style="background-color: #f9fafb; padding: 18px; text-align: center;">
                <p style="font-size: 13px; color: #9ca3af; margin: 0;">
                    © 2025 <strong style="color: #2563eb;">CodiFi</strong>. All rights reserved.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipient_list,
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)




@receiver(post_save, sender=DailyTask)
def create_task_notification(sender, instance, created, **kwargs):
    if created:
        course = instance.course
        students = course.enrolled_students  # ✅ correct (already a list)
        for student in students:
            Notification.objects.create(
                recipient=student,
                actor=course.instructor,
                title=f"New Task: {instance.title}",
                message=f"A new task has been added in {course.title}",
                notif_type='task',
                url=f"/student/course/{course.id}/task/{instance.id}"
            )

@receiver(post_save, sender=LiveSession)
def create_live_notification(sender, instance, created, **kwargs):
    if created:
        course = instance.course
        students = course.enrolled_students
        for student in students:
            Notification.objects.create(
                recipient=student,
                actor=course.instructor,
                title="Today's Live Class Scheduled",
                message=f"Live class for {course.title} starts at {instance.start_time}",
                notif_type='live',
                url=f"/student/course/{course.id}/live"
            )