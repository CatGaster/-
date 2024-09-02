from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created
from .tasks import send_password_reset_email, send_new_user_email, send_order_status_update_email, send_google_welcome_email
from backend.models import ConfirmEmailToken, User, UserProfile


new_user_registered = Signal()
new_order = Signal()
google_user_registered = Signal()


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """
    Отправляем письмо с токеном для сброса пароля
    """
    send_password_reset_email.delay(
        user_email=reset_password_token.user.email,
        token_key=reset_password_token.key
    )

@receiver(post_save, sender=User)
def new_user_registered_signal(sender, instance: User, created: bool, **kwargs):
    """
    Отправляем письмо с подтверждением почты
    """
    if created and not instance.is_active:
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)
        send_new_user_email.delay(
            user_email=instance.email,
            token_key=token.key
        )

@receiver(new_order)
def new_order_signal(user_id, **kwargs):
    """
    Отправляем письмо при изменении статуса заказа
    """
    user = User.objects.get(id=user_id)
    send_order_status_update_email.delay(user_email=user.email)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Обеспечивает сохранение изменений в объекте User в соответствующий UserProfile
    """
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Сохраняет связанный с пользователем UserProfile при каждом сохранении объекта User.
    """
    instance.userprofile.save()


@receiver(post_save, sender=User)
def google_user_registered_signal(sender, instance: User, created: bool, **kwargs):
    """
    Обработчик сигнала для пользователей, зарегистрированных через Google.
    Отправляет приветственное письмо, если у пользователя заполнено поле google_id.
    """
    if created and instance.google_id:
        send_google_welcome_email.delay(
            user_email=instance.email,
            first_name=instance.first_name,
            picture_url=instance.picture
        )
