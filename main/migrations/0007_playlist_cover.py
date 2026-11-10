# Generated manually for playlist covers

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_favoritealbum'),
    ]

    operations = [
        migrations.AddField(
            model_name='playlist',
            name='cover',
            field=models.ImageField(blank=True, null=True, upload_to='playlists/', verbose_name='Обложка'),
        ),
    ]
