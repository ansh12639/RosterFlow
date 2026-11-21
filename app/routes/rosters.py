from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.models import RosterVersion, RosterEntry, Conflict
from app.services.roster_generator import RosterGenerator
from app.services.roster_persistence import save_roster_result

rosters_bp = Blueprint("rosters", __name__, url_prefix="/rosters")


@rosters_bp.route("/")
def index():
    """Display all saved roster versions."""

    versions = RosterVersion.query.order_by(
        RosterVersion.roster_month.desc(), RosterVersion.version_number.desc()
    ).all()

    today = date.today()

    return render_template(
        "rosters/index.html",
        versions=versions,
        current_month=today.month,
        current_year=today.year,
    )


@rosters_bp.route("/generate", methods=["POST"])
def generate():
    """Generate and save a new monthly roster version."""

    try:
        year = int(request.form.get("year", ""))
        month = int(request.form.get("month", ""))

        if year < 2020 or year > 2100:
            raise ValueError("Enter a valid year between 2020 and 2100.")

        if month < 1 or month > 12:
            raise ValueError("Select a valid month.")

        generator = RosterGenerator(year, month)
        result = generator.generate()

        saved = save_roster_result(
            year, month, result, notes="Generated through RosterFlow dashboard"
        )

        flash(
            f"Roster generated successfully. Version {saved['version_number']}: "
            f"{saved['saved_entries']} entries and "
            f"{saved['saved_conflicts']} conflicts.",
            "success",
        )

        return redirect(url_for("rosters.detail", version_id=saved["version_id"]))

    except ValueError as error:
        flash(str(error), "error")

    except Exception as error:
        flash(f"Roster generation failed: {error}", "error")

    return redirect(url_for("rosters.index"))


@rosters_bp.route("/<int:version_id>")
def detail(version_id):
    """Display a saved roster version and its conflicts."""

    version = RosterVersion.query.get_or_404(version_id)

    entries = (
        RosterEntry.query.filter_by(roster_version_id=version_id)
        .order_by(
            RosterEntry.roster_date,
            RosterEntry.shift_start,
            RosterEntry.employee_id,
        )
        .all()
    )

    conflicts = (
        Conflict.query.filter_by(roster_version_id=version_id)
        .order_by(
            Conflict.roster_date,
            Conflict.brand_id,
            Conflict.process_id,
        )
        .all()
    )

    return render_template(
        "rosters/detail.html",
        version=version,
        entries=entries,
        conflicts=conflicts,
    )
