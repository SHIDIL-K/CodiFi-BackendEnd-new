from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.conf import settings

@shared_task
def send_student_welcome_email(*args, **kwargs):
    username = kwargs.get("username")
    email = kwargs.get("email")
    raw_password = kwargs.get("raw_password")

    subject = "Welcome to CodiFi 🎉"

    html_content = f"""
    <html>
    <body style="font-family: 'Inter', 'Segoe UI', sans-serif; background-color: #f8fafc; padding: 40px; margin: 0;">
        <div style="max-width: 650px; margin: auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 6px 18px rgba(0,0,0,0.08);">
            
            <div style="background: linear-gradient(90deg, #2563eb, #9333ea); padding: 24px 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: #9333ea; background: linear-gradient(90deg, #ffffff, #f9fafb); -webkit-background-clip: text;">
                    CodiFi
                </h1>
            </div>

            <div style="padding: 35px 40px;">
                <p style="font-size: 17px; color: #111827;">Hi <strong>{username}</strong>,</p>

                <p style="font-size: 15px; color: #374151; line-height: 1.7;">
                    Welcome to <strong style="color: #9333ea;">CodiFi</strong> 🎉<br>
                    Your student account has been created successfully.
                </p>

                <div style="margin: 25px 0; padding: 18px 22px; background-color: #f0f5ff; border-left: 5px solid #6366f1; border-radius: 10px;">
                    <p style="margin: 0; font-size: 15px; color: #1e3a8a;">
                        <strong>👤 Username:</strong> {username}<br>
                        <strong>🔑 Password:</strong> {raw_password}
                    </p>
                </div>

                <p style="font-size: 15px; color: #374151;">
                    You can log in anytime using the button below:
                </p>

                <p style="text-align: center; margin: 32px 0;">
                    <a href="http://localhost:5173/login"
                       style="background: linear-gradient(90deg, #2563eb, #9333ea);
                              color: white; text-decoration: none;
                              padding: 14px 28px;
                              border-radius: 8px;
                              font-weight: 600;">
                        🔗 Login to CodiFi
                    </a>
                </p>

                <p style="font-size: 14px; color: #6b7280;">
                    If you didn’t create this account, please ignore this email.
                </p>

                <p style="margin-top: 25px; font-size: 15px; color: #111827;">
                    Cheers,<br>
                    <strong style="color: #9333ea;">The CodiFi Team 💻</strong>
                </p>
            </div>

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

    msg = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    return "Email sent successfully"



@shared_task
def send_payment_success_email(username, email, course_title, transaction_id, amount, payment_date):
    subject = "🎉 Payment Successful - Welcome to Your CodiFi Course!"

    html_content = f"""
    <html>
      <body style="font-family: 'Segoe UI', sans-serif; background-color: #f9fafb; padding: 40px;">
        <div style="max-width: 600px; margin: auto; background: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); padding: 30px;">
          
          <div style="background: linear-gradient(90deg, #2563eb, #9333ea); padding: 24px 30px; text-align: center;">
            <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: #9333ea; background: linear-gradient(90deg, #ffffff, #f9fafb); -webkit-background-clip: text;">
                CodiFi
            </h1>
          </div>

          <p style="font-size: 18px; color: #111827;">Hi {username},</p>
          
          <p style="font-size: 16px; color: #374151;">
            Your payment has been <strong>successfully processed</strong>! 🎉
            You are now enrolled in <strong>{course_title}</strong>.
          </p>

          <div style="margin: 25px 0; padding: 20px; background: #f3f4f6; border-radius: 10px;">
            <p style="margin: 8px 0; color: #1f2937;"><strong>💳 Transaction ID:</strong> {transaction_id}</p>
            <p style="margin: 8px 0; color: #1f2937;"><strong>📅 Payment Date:</strong> {payment_date}</p>
            <p style="margin: 8px 0; color: #1f2937;"><strong>📘 Course:</strong> {course_title}</p>
            <p style="margin: 8px 0; color: #1f2937;"><strong>💰 Amount Paid:</strong> ₹{amount}</p>
          </div>

          <p style="font-size: 16px; color: #374151;">
            You can access your course anytime by logging into your CodiFi dashboard.
          </p>

          <div style="text-align: center; margin-top: 25px;">
            <a href="http://localhost:5173/login"
               style="background: linear-gradient(to right, #2563eb, #9333ea);
                      color: white; text-decoration: none; padding: 12px 25px;
                      border-radius: 8px; font-weight: 600; display: inline-block;">
              Go to Dashboard
            </a>
          </div>

          <p style="font-size: 15px; color: #6b7280; margin-top: 30px; text-align: center;">
            Thank you for choosing <strong>CodiFi</strong> 💻<br>
            We’re excited to have you on board!
          </p>
        </div>
      </body>
    </html>
    """

    text_content = strip_tags(html_content)

    email_obj = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    email_obj.attach_alternative(html_content, "text/html")
    email_obj.send()

    return "Payment confirmation email sent."

