import click

from .db import init_db


def register_cli(app):
    @app.cli.command("init-db")
    def init_db_command():
        init_db()
        click.echo("Database initialised.")

    @app.cli.command("seed")
    @click.option("--samples", is_flag=True, help="Also add a few clearly-labelled sample gigs.")
    def seed_command(samples):
        from .seed import seed

        venues, gigs = seed(with_samples=samples)
        click.echo(f"Seeded {venues} venue(s) and {gigs} gig(s).")

    @app.cli.command("import-venues")
    @click.argument("json_file", type=click.Path(exists=True))
    def import_venues_command(json_file):
        """Import venues from a JSON file like app/data/echo_venues.json.
        Skips venues that already exist (matched by name + town, case-insensitive)."""
        from .import_venues import import_venues

        added, skipped = import_venues(json_file)
        click.echo(f"Added {added} new venue(s), skipped {skipped} already present.")
