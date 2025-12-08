from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from django.utils.translation import gettext_lazy


class User(AbstractBaseUser):
    class UserType(models.TextChoices):
        worker = 'worker', gettext_lazy('worker')
        client = 'client', gettext_lazy('client')

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    phone_number = models.CharField(max_length=255, unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, null=True, blank=True)
    user_type = models.CharField(
        gettext_lazy('user type'),
        choices=UserType.choices,
        max_length=255,
        default=UserType.worker,
    )
    # photo = models.ForeignKey('files.File', on_delete=models.SET_NULL, null=True, blank=True,
    #                          related_name='+', verbose_name=gettext_lazy('photo'))
    is_active = models.BooleanField(gettext_lazy('active'), default=True)

    class Meta:
        verbose_name = gettext_lazy('user')
        verbose_name_plural = gettext_lazy('user')
        #db_table = 'user\".\"users'
        # permissions = (
        #     ("view_documents", "Can view documents"),
        #     ("update_documents", "Can update documents"),
        #     ("delete_documents", "Can delete documents"),
        # )
        #superuser roman 1111

        # db psql -U postgres_user buyer
        #\q

    def get_full_name(self) -> str:
        """Возвращает полное имя пользователя."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        """Возвращает короткое имя пользователя."""
        return self.first_name

    def __str__(self) -> str:
        return self.get_full_name() or self.phone_number or str(self.id)