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
