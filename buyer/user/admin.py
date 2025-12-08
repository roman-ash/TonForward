from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


# class UserAdmin(BaseUserAdmin):
#     search_fields = ('phone_number',)


admin.site.register(User)
