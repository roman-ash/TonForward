# Generated manually to handle NULL phone_number values

from django.db import migrations, models


def populate_phone_numbers(apps, schema_editor):
    """Заполняет NULL значения phone_number уникальными значениями."""
    User = apps.get_model('user', 'User')
    
    # Находим всех пользователей с NULL phone_number
    users_with_null_phone = User.objects.filter(phone_number__isnull=True)
    
    for user in users_with_null_phone:
        # Генерируем уникальный phone_number на основе ID и email (если есть)
        # Формат: user_{id} или user_{id}_{email_hash} если email есть
        if user.email:
            # Используем часть email для уникальности
            email_part = user.email.split('@')[0][:10]  # Берем первые 10 символов до @
            phone_number = f'user_{user.id}_{email_part}'
        else:
            phone_number = f'user_{user.id}'
        
        # Убеждаемся, что номер уникален (на случай если уже существует)
        counter = 1
        original_phone = phone_number
        while User.objects.filter(phone_number=phone_number).exclude(id=user.id).exists():
            phone_number = f'{original_phone}_{counter}'
            counter += 1
        
        user.phone_number = phone_number
        user.save(update_fields=['phone_number'])


def reverse_populate_phone_numbers(apps, schema_editor):
    """Обратная операция - устанавливает phone_number в NULL для временных значений."""
    User = apps.get_model('user', 'User')
    # Находим временные номера (начинаются с 'user_')
    User.objects.filter(phone_number__startswith='user_').update(phone_number=None)


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0001_initial'),
    ]

    operations = [
        # Шаг 1: Заполняем NULL значения уникальными номерами
        migrations.RunPython(
            populate_phone_numbers,
            reverse_populate_phone_numbers,
        ),
        # Шаг 2: Изменяем поле на non-nullable и добавляем unique constraint
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
