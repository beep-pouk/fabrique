# Rattrapage (J5) : une session importée de Bramble avant J5 reçoit les réglages que l'import pose désormais (format F1, assistant fini, ce qui
# rend chaque vidéo différente) ; sans eux, le garde-fou refuserait « Fabriquer ». Rien n'est écrasé.

from django.db import migrations

DIFFERENCE = ("Chaque épisode a son propre scénario, écrit pour lui, et le héros, l'ami et le lieu de sa fiche du calendrier éditorial "
              "(repris de Bramble Studio ; à préciser dans Règles).")  # = session/bramble.py


def rattraper(apps, schema_editor):
    Reglage = apps.get_model("session", "Reglage")
    base = schema_editor.connection.alias
    if not Reglage.objects.using(base).filter(cle="origine", valeur="bramble").exists():
        return
    for cle, valeur in (("formats", '["F1"]'), ("format", "F1"), ("assistant", "fini"), ("difference", DIFFERENCE)):
        Reglage.objects.using(base).get_or_create(cle=cle, defaults={"valeur": valeur})


class Migration(migrations.Migration):

    dependencies = [
        ('session', '0009_univers_droits'),
    ]

    operations = [
        migrations.RunPython(rattraper, migrations.RunPython.noop),
    ]
