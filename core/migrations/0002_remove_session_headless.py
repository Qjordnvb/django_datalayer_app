# Generated by Django 4.2.7 on 2025-04-17 16:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='session',
            name='headless',
        ),
    ]
