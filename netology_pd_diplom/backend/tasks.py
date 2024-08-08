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