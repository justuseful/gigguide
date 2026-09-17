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

    @app.cli.command("import-gigs")
    @click.argument("json_file", type=click.Path(exists=True))
    def import_gigs_command(json_file):
        """Import gigs from a JSON file like app/data/echo_gigs.json.
        Skips gigs that already exist (matched by venue + date + time + title).
        Gigs whose venue name doesn't match one already in the venues table are
        skipped and counted as unmatched, rather than guessed at."""
        from .import_gigs import import_gigs

        added, skipped, unmatched = import_gigs(json_file)
        click.echo(
            f"Added {added} new gig(s), skipped {skipped} already present, "
            f"{unmatched} unmatched venue(s)."
        )

    @app.cli.command("merge-venues")
    @click.argument("keep_slug")
    @click.argument("remove_slug")
    def merge_venues_command(keep_slug, remove_slug):
        """Move all gigs from REMOVE_SLUG onto KEEP_SLUG, then delete REMOVE_SLUG.
        For duplicate venues (e.g. a manually-added one and a differently-named
        one picked up by the Echo scrape)."""
        from .merge_venues import merge_venues

        moved, keep_name, remove_name = merge_venues(keep_slug, remove_slug)
        click.echo(f"Moved {moved} gig(s) from '{remove_name}' into '{keep_name}'. '{remove_name}' deleted.")

    @app.cli.command("import-facebook-events")
    def import_facebook_events_command():
        """Pull upcoming events from each venue's Facebook Page (set via the
        "Facebook Page ID" field on that venue) and add any not already listed.
        Uses that venue's own Page Access Token if set (works today, for pages
        you admin), otherwise falls back to FACEBOOK_APP_ID/FACEBOOK_APP_SECRET,
        which only works once Meta approves Page Public Content Access."""
        from .facebook_events import import_facebook_events

        report = import_facebook_events(app.config["FACEBOOK_APP_ID"], app.config["FACEBOOK_APP_SECRET"])
        if not report:
            click.echo("No venues have a Facebook Page ID set yet - add one from the venue edit page.")
            return
        for venue_name, result in report.items():
            if "error" in result:
                click.echo(f"{venue_name}: FAILED - {result['error']}")
            else:
                click.echo(f"{venue_name}: added {result['added']} new gig(s) ({result['found']} events found)")
