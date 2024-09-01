from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from backend.models import ConfirmEmailToken, User




@shared_task
def send_password_reset_email(user_email, token_key):
    msg = EmailMultiAlternatives(
        subject=f"Password Reset Token for {user_email}",
        body=token_key,
        from_email=settings.EMAIL_HOST_USER,
        to=[user_email]
    )
    msg.send()

@shared_task
def send_new_user_email(user_email, token_key):
    msg = EmailMultiAlternatives(
        subject=f"Confirm Token for {user_email}",
        body=token_key,
        from_email=settings.EMAIL_HOST_USER,
        to=[user_email]
    )
    msg.send()

@shared_task
def send_order_status_update_email(user_email):
    msg = EmailMultiAlternatives(
        subject="Обновление статуса заказа",
        body="Заказ сформирован",
        from_email=settings.EMAIL_HOST_USER,
        to=[user_email]
    )
    msg.send()


@shared_task
def send_google_welcome_email(user_email, first_name, picture_url):
    """
    Отправляет приветственное письмо новому пользователю, зарегистрированному через Google.
    """
    subject = "Добро пожаловать!"
    body = f"Здравствуйте, {first_name}!\n\nСпасибо за регистрацию через Google."

    # Если нужно добавить картинку, можно использовать HTML письмо
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=settings.EMAIL_HOST_USER,
        to=[user_email]
    )
    msg.attach_alternative(
        f"""
        <html>
        <body>
            <p>Здравствуйте, {first_name}!</p>
            <p>Спасибо за регистрацию через Google.</p>
            <img src="{picture_url}" alt="Profile Picture" width="100" height="100"/>
        </body>
        </html>
        """, 
        "text/html"
    )
    msg.send()