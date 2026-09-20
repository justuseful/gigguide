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

    @app.cli.command("merge-performers")
    @click.argument("keep_slug")
    @click.argument("remove_slug")
    def merge_performers_command(keep_slug, remove_slug):
        """Move all gig links from REMOVE_SLUG onto KEEP_SLUG, then delete REMOVE_SLUG.
        For duplicate performers (e.g. a typo or "Matt"/"Matthew"-style name
        variant picked up by the Echo scrape)."""
        from .merge_performers import merge_performers

        moved, keep_name, remove_name = merge_performers(keep_slug, remove_slug)
        click.echo(f"Moved {moved} gig link(s) from '{remove_name}' into '{keep_name}'. '{remove_name}' deleted.")

    @app.cli.command("ensure-performer")
    @click.argument("name")
    def ensure_performer_command(name):
        """Find a performer by name (case-insensitive), or create a new profile
        for them if none exists yet. Prints the slug either way."""
        from .update_performer import ensure_performer

        slug, created = ensure_performer(name)
        click.echo(f"{'Created' if created else 'Found'} '{name}' -> slug '{slug}'")

    @app.cli.command("update-performer")
    @click.argument("slug")
    @click.option("--bio", help="Replace the profile bio text.")
    @click.option("--youtube-id", help="YouTube video ID for the featured video.")
    @click.option("--social-url", help="Instagram or Facebook post/video URL.")
    @click.option("--related", help="Comma-separated slugs of other performers to show as 'Also featuring'.")
    @click.option("--website", help="Website link (or e.g. a Spotify track/artist link).")
    @click.option("--instagram", help="Instagram handle (without the @).")
    @click.option("--based-in", help="Town/region they're based in, e.g. 'Byron Bay'.")
    @click.option("--booking", help="Booking contact: email, phone, manager, 'via Instagram DM', etc.")
    def update_performer_command(slug, bio, youtube_id, social_url, related, website, instagram, based_in, booking):
        """Set one or more fields on an existing performer's profile (e.g. for
        content added from a video/story rather than through the admin form)."""
        from .update_performer import update_performer

        fields = {}
        if bio is not None:
            fields["bio"] = bio
        if youtube_id is not None:
            fields["youtube_id"] = youtube_id
        if social_url is not None:
            fields["social_url"] = social_url
        if related is not None:
            fields["related_performers"] = related
        if website is not None:
            fields["website"] = website
        if instagram is not None:
            fields["instagram"] = instagram
        if based_in is not None:
            fields["based_in"] = based_in
        if booking is not None:
            fields["booking"] = booking
        name = update_performer(slug, **fields)
        click.echo(f"Updated '{name}'.")

    @app.cli.command("link-performers")
    def link_performers_command():
        """Backfill performer links for every existing gig by splitting its
        title on "+"/",". Safe to re-run - only adds links that don't already
        exist. New gigs from `import-gigs` are linked automatically as they're
        added; this is for gigs imported before that was in place."""
        from .db import get_db
        from .link_performers import link_performers_from_titles

        result = link_performers_from_titles(get_db())
        click.echo(
            f"Processed {result['gigs_processed']} gig(s), {result['gigs_with_performers']} had "
            f"performer(s) to link. Created {result['performers_created']} new performer(s), "
            f"added {result['links_added']} gig-performer link(s)."
        )

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
