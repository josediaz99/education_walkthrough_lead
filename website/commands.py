import click
from flask.cli import with_appcontext
from .models import db, Tag

@click.command("seed-tags")
@with_appcontext
def seed_tags():
    names = ["Professional Development", "IB", "AP", "AVID"]
    existing = {t.name for t in Tag.query.filter(Tag.name.in_(names)).all()}
    for name in names:
        if name not in existing:
            db.session.add(Tag(name=name))
    db.session.commit()
    click.echo("Seeded default tags.")