from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('session', '0004_publication'),
    ]

    operations = [
        migrations.CreateModel(
            name='Publication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('langue', models.CharField(max_length=10)),
                ('dossier', models.CharField(max_length=10)),
                ('fichier', models.CharField(default='', max_length=200)),
                ('miniature', models.CharField(default='', max_length=200)),
                ('titre', models.CharField(default='', max_length=100)),
                ('description', models.TextField(default='')),
                ('tags', models.JSONField(default=list)),
                ('playlist', models.CharField(default='', max_length=100)),
                ('enfants', models.BooleanField(default=True)),
                ('ia', models.BooleanField(default=True)),
                ('planifiee_le', models.DateTimeField(null=True)),
                ('non_repertorie', models.BooleanField(default=False)),
                ('simulation', models.BooleanField(default=False)),
                ('statut', models.CharField(default='brouillon', max_length=20)),
                ('identifiant_youtube', models.CharField(default='', max_length=50)),
                ('envoi', models.JSONField(default=dict)),
                ('versions', models.JSONField(default=list)),
                ('video', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='publications', to='session.video')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('video', 'langue'), name='publication_unique')],
            },
        ),
    ]
