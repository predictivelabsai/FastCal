"""Server-rendered FastCal application pages."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from fasthtml.common import *  # noqa: F403

APP_CSS = """
:root{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--accent:#0891b2;--tint:#ecfeff}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:#f8fafc;font-family:Inter,ui-sans-serif,system-ui,sans-serif}
a{color:inherit}.shell{max-width:1160px;margin:auto;padding:0 24px}.top{height:68px;display:flex;align-items:center;gap:22px;border-bottom:1px solid var(--line);background:#fff}.top .shell{width:100%;display:flex;align-items:center}.brand{font-size:21px;font-weight:800;text-decoration:none}.brand b{color:var(--accent)}.nav{display:flex;gap:18px;margin-left:34px}.nav a{text-decoration:none;color:#475569;font-size:14px}.user{margin-left:auto;color:var(--muted);font-size:14px}.user a{margin-left:14px}
main.shell{padding-top:34px;padding-bottom:60px}.hero-row{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:28px}h1{font-size:32px;margin:0 0 8px}h2{font-size:20px;margin:0 0 18px}p{line-height:1.55}.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px;box-shadow:0 1px 2px #0f172a0b}.card h3{margin:0 0 8px}.pill{display:inline-block;padding:4px 9px;border-radius:999px;background:var(--tint);color:#0e7490;font-size:12px;font-weight:700}.btn{display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:9px;padding:10px 15px;background:var(--accent);color:white;text-decoration:none;font-weight:700;cursor:pointer}.btn.secondary{background:white;color:var(--ink);border:1px solid var(--line)}
form.panel{max-width:720px;background:#fff;border:1px solid var(--line);border-radius:14px;padding:24px}.field{margin-bottom:16px}.field label{display:block;font-size:13px;font-weight:700;margin-bottom:6px}.field input,.field textarea,.field select{width:100%;border:1px solid #cbd5e1;border-radius:9px;padding:10px 11px;font:inherit}.field textarea{min-height:90px}.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}.slots{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:9px}.slot{display:block;width:100%;padding:10px;border:1px solid #bae6fd;background:#fff;border-radius:9px;color:#0e7490;font-weight:700;cursor:pointer}.booking-wrap{max-width:900px;margin:38px auto;padding:0 20px}.booking-head{text-align:center;margin-bottom:24px}.notice{padding:12px 14px;background:var(--tint);border:1px solid #a5f3fc;border-radius:9px;margin:14px 0}.danger{color:#b91c1c}.list{width:100%;border-collapse:collapse}.list th,.list td{text-align:left;padding:12px;border-bottom:1px solid var(--line);font-size:14px}.empty{text-align:center;padding:42px;color:var(--muted)}
@media(max-width:700px){.nav{display:none}.shell{padding-left:16px;padding-right:16px}.row{grid-template-columns:1fr}.hero-row{display:block}.hero-row .btn{margin-top:14px}.list{display:block;overflow:auto}}
"""


def page(identity, active: str, *content):
    return Html(
        Head(
            Title("FastCal"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Style(APP_CSS),
        ),
        Body(
            Header(
                Div(
                    A("Fast", B("Cal"), href="/app", cls="brand"),
                    Nav(
                        A("Event types", href="/app"),
                        A("Bookings", href="/bookings"),
                        A("Availability", href="/availability"),
                        A("Teams", href="/teams"),
                        cls="nav",
                    ),
                    Div(identity["name"], A("Sign out", href="/logout"), cls="user"),
                    cls="shell",
                ),
                cls="top",
            ),
            Main(*content, cls="shell"),
        ),
    )


def dashboard(identity, event_types, upcoming):
    cards = [
        Div(
            Span(item.scheduling_type.replace("_", " ").title(), cls="pill"),
            H3(item.title),
            P(f"{item.duration_minutes} minutes · {item.timezone}", cls="muted"),
            A("Open booking page", href=f"/book/{item.organisation_slug}/{item.slug}"),
            cls="card",
        )
        for item in event_types
    ]
    return page(
        identity,
        "event-types",
        Div(
            Div(
                H1("Event types"),
                P(
                    "Individual, collective, and fair round-robin scheduling.",
                    cls="muted",
                ),
            ),
            A("New event type", href="/event-types/new", cls="btn"),
            cls="hero-row",
        ),
        Div(*cards, cls="grid")
        if cards
        else Div("Create your first scheduling link.", cls="card empty"),
        H2("Upcoming bookings", style="margin-top:34px"),
        booking_table(upcoming),
    )


def booking_table(bookings):
    if not bookings:
        return Div("No bookings yet.", cls="card empty")
    return Table(
        Thead(Tr(Th("Meeting"), Th("Guest"), Th("When"), Th("Status"))),
        Tbody(
            *[
                Tr(
                    Td(row.title),
                    Td(row.guest_name, Br(), Small(row.guest_email, cls="muted")),
                    Td(row.starts_at.strftime("%d %b %Y · %H:%M UTC")),
                    Td(Span(row.status.title(), cls="pill")),
                )
                for row in bookings
            ]
        ),
        cls="card list",
    )


def event_type_form(identity, schedules, teams, users, error=""):
    return page(
        identity,
        "event-types",
        H1("New event type"),
        P("Choose how hosts should be assigned when someone books.", cls="muted"),
        P(error, cls="danger") if error else None,
        Form(
            Div(
                Label("Title"),
                Input(
                    name="title", required=True, placeholder="30 minute introduction"
                ),
                cls="field",
            ),
            Div(
                Label("Description"),
                Textarea(name="description", placeholder="What should guests expect?"),
                cls="field",
            ),
            Div(
                Div(
                    Label("Duration (minutes)"),
                    Input(
                        name="duration_minutes",
                        type="number",
                        value="30",
                        min="5",
                        max="480",
                    ),
                    cls="field",
                ),
                Div(
                    Label("Scheduling type"),
                    Select(
                        Option("Individual", value="individual"),
                        Option("Collective", value="collective"),
                        Option("Round robin", value="round_robin"),
                        name="scheduling_type",
                    ),
                    cls="field",
                ),
                cls="row",
            ),
            Div(
                Div(
                    Label("Schedule"),
                    Select(
                        *[Option(row.name, value=row.id) for row in schedules],
                        name="schedule_id",
                    ),
                    cls="field",
                ),
                Div(
                    Label("Team"),
                    Select(
                        Option("No team", value=""),
                        *[Option(row.name, value=row.id) for row in teams],
                        name="team_id",
                    ),
                    cls="field",
                ),
                cls="row",
            ),
            Div(
                Label("Hosts"),
                P(
                    "Comma-separated member emails. Leave blank to use yourself.",
                    cls="muted",
                ),
                Input(
                    name="host_emails", placeholder="alice@example.com, bob@example.com"
                ),
                cls="field",
            ),
            Div(
                Div(
                    Label("Minimum notice (minutes)"),
                    Input(
                        name="minimum_notice_minutes",
                        type="number",
                        value="240",
                        min="0",
                    ),
                    cls="field",
                ),
                Div(
                    Label("Buffer after (minutes)"),
                    Input(
                        name="after_buffer_minutes", type="number", value="10", min="0"
                    ),
                    cls="field",
                ),
                cls="row",
            ),
            Div(
                Label("Location"),
                Select(
                    Option("FastMeet", value="fastmeet"),
                    Option("Custom location", value="custom"),
                    name="location_type",
                ),
                cls="field",
            ),
            Button("Create event type", cls="btn", type="submit"),
            method="post",
            action="/event-types",
            cls="panel",
        ),
    )


def public_booking(event_type, organisation, slots, message=""):
    tz = ZoneInfo(event_type.timezone)
    return Html(
        Head(
            Title(f"{event_type.title} · FastCal"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Style(APP_CSS),
        ),
        Body(
            Main(
                Div(
                    H1(event_type.title),
                    P(organisation.name, cls="muted"),
                    P(event_type.description),
                    P(
                        f"{event_type.duration_minutes} minutes · {event_type.timezone}",
                        cls="pill",
                    ),
                    cls="booking-head",
                ),
                Div(message, cls="notice") if message else None,
                Div(
                    H2("Choose a time"),
                    Div(
                        *[
                            Form(
                                Input(
                                    type="hidden",
                                    name="starts_at",
                                    value=slot.starts_at.isoformat(),
                                ),
                                Input(
                                    type="hidden",
                                    name="ends_at",
                                    value=slot.ends_at.isoformat(),
                                ),
                                Button(
                                    slot.starts_at.astimezone(tz).strftime(
                                        "%a %d %b · %H:%M"
                                    ),
                                    cls="slot",
                                    type="submit",
                                ),
                                method="get",
                            )
                            for slot in slots[:60]
                        ],
                        cls="slots",
                    )
                    if slots
                    else P("No times are currently available.", cls="muted"),
                    cls="card",
                ),
                cls="booking-wrap",
            )
        ),
    )


def public_booking_details(event_type, organisation, starts_at, ends_at, error=""):
    local = starts_at.astimezone(ZoneInfo(event_type.timezone))
    return Html(
        Head(
            Title(f"Book {event_type.title}"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Style(APP_CSS),
        ),
        Body(
            Main(
                Div(
                    H1(event_type.title),
                    P(organisation.name, cls="muted"),
                    P(local.strftime("%A, %d %B %Y · %H:%M %Z"), cls="notice"),
                    cls="booking-head",
                ),
                P(error, cls="danger") if error else None,
                Form(
                    Input(type="hidden", name="starts_at", value=starts_at.isoformat()),
                    Input(type="hidden", name="ends_at", value=ends_at.isoformat()),
                    Div(
                        Label("Your name"),
                        Input(name="guest_name", required=True, autocomplete="name"),
                        cls="field",
                    ),
                    Div(
                        Label("Email"),
                        Input(
                            name="guest_email",
                            type="email",
                            required=True,
                            autocomplete="email",
                        ),
                        cls="field",
                    ),
                    Div(
                        Label("Timezone"),
                        Input(
                            name="guest_timezone",
                            value=event_type.timezone,
                            required=True,
                        ),
                        cls="field",
                    ),
                    Div(Label("Notes"), Textarea(name="notes"), cls="field"),
                    Button("Confirm booking", type="submit", cls="btn"),
                    method="post",
                    cls="panel",
                ),
                cls="booking-wrap",
            )
        ),
    )


def booking_success(booking, cancel_token):
    return Html(
        Head(
            Title("Booking confirmed · FastCal"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Style(APP_CSS),
        ),
        Body(
            Main(
                Div(
                    H1("You’re booked."),
                    P(f"{booking.title} with {booking.guest_name}"),
                    P(booking.starts_at.strftime("%d %B %Y · %H:%M UTC"), cls="notice"),
                    A(
                        "Cancel booking",
                        href=f"/bookings/cancel/{cancel_token}",
                        cls="btn secondary",
                    ),
                    cls="card",
                ),
                cls="booking-wrap",
            )
        ),
    )


def availability_page(identity, schedule, rules, saved=False):
    by_day = {rule.weekday: rule for rule in rules}
    first = next(iter(by_day.values()), None)
    selected = ",".join(str(day) for day in sorted(by_day))
    return page(
        identity,
        "availability",
        H1("Availability"),
        P("Set the default working window used by your event types.", cls="muted"),
        Div("Availability saved.", cls="notice") if saved else None,
        Form(
            Div(
                Label("Working weekdays"),
                Input(
                    name="weekdays",
                    value=selected or "0,1,2,3,4",
                    placeholder="0,1,2,3,4",
                ),
                P("Monday is 0; Sunday is 6.", cls="muted"),
                cls="field",
            ),
            Div(
                Div(
                    Label("Start"),
                    Input(
                        name="start_time",
                        type="time",
                        value=(
                            first.start_time.strftime("%H:%M") if first else "09:00"
                        ),
                    ),
                    cls="field",
                ),
                Div(
                    Label("End"),
                    Input(
                        name="end_time",
                        type="time",
                        value=(first.end_time.strftime("%H:%M") if first else "17:00"),
                    ),
                    cls="field",
                ),
                cls="row",
            ),
            Div(
                Label("Timezone"),
                Input(name="timezone", value=schedule.timezone),
                cls="field",
            ),
            Button("Save availability", cls="btn", type="submit"),
            method="post",
            cls="panel",
        ),
    )


def teams_page(identity, teams, members, message=""):
    return page(
        identity,
        "teams",
        H1("Teams"),
        P("Group hosts for collective and round-robin event types.", cls="muted"),
        Div(message, cls="notice") if message else None,
        Div(
            *[
                Div(H3(team.name), P(team.slug, cls="muted"), cls="card")
                for team in teams
            ],
            cls="grid",
        )
        if teams
        else Div("No teams yet.", cls="card empty"),
        H2("Create team", style="margin-top:34px"),
        Form(
            Div(Label("Team name"), Input(name="name", required=True), cls="field"),
            Div(
                Label("Member emails"),
                Input(
                    name="member_emails",
                    placeholder="alice@example.com, bob@example.com",
                ),
                cls="field",
            ),
            Button("Create team", cls="btn", type="submit"),
            method="post",
            cls="panel",
        ),
    )
