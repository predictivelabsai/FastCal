"""FastCal HTML views."""

from fasthtml.common import *

from seo import seo_meta

PARTNERS = (
    (
        "SAASPASS",
        "https://saaspass.com/",
        "https://saaspass.com/_next/static/assets/0176aeff921f6359fee88e796be31ace.png",
        "Full-stack identity and access management spanning MFA, SSO, passwordless access and integration APIs.",
    ),
    (
        "Sixty Four",
        "https://sixtyfour.ee/",
        "https://sixtyfour.ee/favicon.ico",
        "A senior Tallinn technology studio delivering software, AI consultancy, service design and public-sector programmes.",
    ),
    (
        "EDI Labs",
        "https://edilabs.tech/",
        "https://edilabs.tech/static/favicon.svg",
        "AI and data engineering for document intelligence, forecasting, geospatial systems and agentic workflows.",
    ),
    (
        "Predictive Labs",
        "https://predictivelabs.ai/",
        "https://predictivelabs.ai/static/favicon.svg",
        "Auditable AI systems for health, defence, public management, mobility and financial services.",
    ),
    (
        "Consistente",
        "https://consistente.tech/",
        "https://consistente.tech/static/favicon.svg",
        "Enterprise AI delivery across financial services, healthcare, the public sector and technology.",
    ),
    (
        "Manmouna Technologies",
        "https://manmouna.tech/",
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%230B1E14'/%3E%3Cpath d='M32 12 52 32 32 52 12 32Z' fill='%2334D399'/%3E%3Cpath d='M32 22 42 32 32 42 22 32Z' fill='%230B1E14'/%3E%3C/svg%3E",
        "Auditable-by-design AI systems for European public services across health, defence, public management and mobility.",
    ),
)

CSS = """
:root{--accent:#0891b2;--ink:#172033;--muted:#667085;--line:#e4e7ec;--tint:#ecfeff}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,sans-serif;color:var(--ink);background:#fff}a{color:inherit}
.nav{height:68px;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 max(22px,calc((100vw - 1180px)/2));gap:28px}.brand{font-size:20px;font-weight:800;text-decoration:none}.brand b{color:var(--accent)}.nav .signin{margin-left:auto;padding:10px 17px;border-radius:10px;background:var(--accent);color:#fff;text-decoration:none;font-weight:700}
.hero{max-width:1180px;margin:auto;min-height:640px;display:grid;grid-template-columns:1fr 1fr;gap:70px;align-items:center;padding:70px 22px}.eyebrow{color:var(--accent);font-size:11px;font-weight:800;letter-spacing:.16em;text-transform:uppercase}.hero h1{font-size:60px;line-height:1.02;letter-spacing:-.055em;margin:20px 0}.hero p{font-size:18px;line-height:1.65;color:var(--muted)}.cta{display:inline-flex;margin-top:22px;background:var(--accent);color:#fff;text-decoration:none;padding:14px 20px;border-radius:12px;font-weight:800}
.preview{background:var(--tint);border:1px solid #c7f0f5;border-radius:22px;padding:22px;box-shadow:0 30px 70px rgba(8,145,178,.15)}.week{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.day{height:300px;background:#fff;border-radius:10px;padding:10px;font-size:11px}.event{margin-top:35px;padding:9px;border-left:3px solid var(--accent);background:var(--tint);border-radius:5px;font-weight:700}.features{background:#f8fafc;padding:90px 22px}.features>div{max-width:1180px;margin:auto;display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.features article{background:#fff;border:1px solid var(--line);padding:28px;border-radius:16px}.features p{color:var(--muted);line-height:1.55}
.partners{max-width:1180px;margin:auto;padding:82px 22px;scroll-margin-top:80px}.partners h2{font-size:34px;margin:10px 0}.partners>p{max-width:720px;color:var(--muted);line-height:1.65}.partner-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin-top:30px}.partner-card{min-width:0;border:1px solid var(--line);border-radius:16px;padding:18px;text-decoration:none}.partner-card img{width:44px;height:44px;object-fit:contain}.partner-card small{display:block;margin-top:14px;color:var(--accent);font-weight:800;text-transform:uppercase;letter-spacing:.08em}.partner-card h3{margin:7px 0}.partner-card p{font-size:12px;line-height:1.55;color:var(--muted)}
.shell{display:grid;grid-template-columns:240px 1fr;min-height:100vh}.side{padding:24px;background:#f8fafc;border-right:1px solid var(--line)}.side .new{display:block;margin:30px 0;padding:12px;background:var(--accent);color:#fff;border-radius:10px;text-decoration:none;text-align:center}.main{padding:40px;max-width:1100px}.top{display:flex;align-items:center}.top a{margin-left:auto}.events{display:grid;gap:10px}.event-row{display:grid;grid-template-columns:150px 1fr auto;gap:18px;padding:18px;border:1px solid var(--line);border-radius:12px}.event-row p{margin:5px 0 0;color:var(--muted)}form.card{max-width:720px;display:grid;grid-template-columns:1fr 1fr;gap:15px;border:1px solid var(--line);padding:25px;border-radius:15px}label{display:grid;gap:7px;font-size:12px;font-weight:700}input,select,textarea{border:1px solid #d0d5dd;border-radius:9px;padding:11px;font:inherit}.wide{grid-column:1/-1}.btn{border:0;background:var(--accent);color:#fff;padding:12px 17px;border-radius:9px;font-weight:700;cursor:pointer}
@media(max-width:980px){.partner-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:760px){.hero{grid-template-columns:1fr;min-height:0}.hero h1{font-size:44px}.preview{display:none}.features>div,.partner-grid{grid-template-columns:1fr}.shell{display:block}.side{display:none}.main{padding:25px 16px}.event-row{grid-template-columns:1fr}form.card{grid-template-columns:1fr}.wide{grid-column:auto}}
"""


def partner_section():
    return Section(
        Span("Partners", cls="eyebrow"),
        H2("Connect with trusted integration specialists."),
        P(
            "Identity, software delivery, data engineering and applied-AI expertise for FastSME implementations."
        ),
        Div(
            *[
                A(
                    Img(src=logo, alt=f"{name} logo", loading="lazy"),
                    Small("Integration Partner"),
                    H3(name),
                    P(description),
                    href=url,
                    target="_blank",
                    rel="noopener noreferrer",
                    cls="partner-card",
                )
                for name, url, logo, description in PARTNERS
            ],
            cls="partner-grid",
        ),
        id="partners",
        cls="partners",
    )


def landing():
    return Html(
        Head(
            Title("FastCal — Open team calendar"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            *seo_meta(title="FastCal — Open team calendar"),
            Style(CSS),
        ),
        Body(
            Nav(
                A("Fast", B("Cal"), href="/", cls="brand"),
                A("Partners", href="#partners"),
                A("Developers", href="/developers"),
                A("FastOffice", href="/auth/suite"),
                A("Sign In with Google", href="/auth/google", cls="signin"),
                cls="nav",
            ),
            Main(
                Section(
                    Div(
                        Span("OPEN TEAM CALENDAR", cls="eyebrow"),
                        H1("Make time work for everyone."),
                        P(
                            "Coordinate calendars, availability, recurring events, reminders and FastMeet links in one open workspace."
                        ),
                        A("Open FastCal", href="/auth/suite", cls="cta"),
                    ),
                    Div(
                        Div(
                            *[
                                Div(
                                    Strong(day),
                                    Div("Team planning", cls="event")
                                    if day == "Tue"
                                    else None,
                                    cls="day",
                                )
                                for day in ("Mon", "Tue", "Wed", "Thu", "Fri")
                            ],
                            cls="week",
                        ),
                        cls="preview",
                    ),
                    cls="hero",
                ),
                Section(
                    Div(
                        Article(
                            H3("Shared calendars"),
                            P(
                                "Keep team schedules visible without giving up ownership."
                            ),
                        ),
                        Article(
                            H3("Availability and reminders"),
                            P(
                                "Coordinate across time zones and keep commitments on track."
                            ),
                        ),
                        Article(
                            H3("FastMeet connected"),
                            P(
                                "Attach meeting rooms and carry scheduling into follow-through."
                            ),
                        ),
                    ),
                    cls="features",
                ),
                partner_section(),
            ),
        ),
    )


def shell(identity: dict, content):
    return Html(
        Head(
            Title("FastCal"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Style(CSS),
        ),
        Body(
            Div(
                Aside(
                    A("Fast", B("Cal"), href="/", cls="brand"),
                    A("+ New event", href="/events/new", cls="new"),
                    P(identity["org_name"]),
                    Small(identity["email"]),
                    P(A("FastOffice", href="/launch/office")),
                    P(A("Sign out", href="/logout")),
                    cls="side",
                ),
                Main(content, cls="main"),
                cls="shell",
            )
        ),
    )


def home(identity: dict, rows: list[dict]):
    items = [
        Article(
            Div(Strong(r["starts_at"][0:10]), Br(), Small(r["starts_at"][11:16])),
            Div(
                H3(r["title"]),
                P(
                    " · ".join(
                        x
                        for x in (r["calendar_name"], r["location"], r["attendees"])
                        if x
                    )
                ),
            ),
            Form(
                Input(type="hidden", name="event_id", value=r["id"]),
                Button("Delete", cls="btn"),
                method="post",
                action="/events/delete",
            ),
            cls="event-row",
        )
        for r in rows
    ]
    return shell(
        identity,
        (
            Div(
                Div(Span("CALENDAR", cls="eyebrow"), H1("Upcoming events")),
                A("Search", href="/search"),
                cls="top",
            ),
            Div(*(items or [P("No events yet.")]), cls="events"),
        ),
    )


def event_form(identity: dict, calendars: list[dict]):
    return shell(
        identity,
        (
            Span("NEW EVENT", cls="eyebrow"),
            H1("Schedule time"),
            Form(
                Label("Title", Input(name="title", required=True)),
                Label(
                    "Calendar",
                    Select(
                        *[Option(c["name"], value=c["id"]) for c in calendars],
                        name="calendar_id",
                    ),
                ),
                Label(
                    "Starts",
                    Input(type="datetime-local", name="starts_at", required=True),
                ),
                Label(
                    "Ends", Input(type="datetime-local", name="ends_at", required=True)
                ),
                Label("Time zone", Input(name="timezone", value="Europe/Tallinn")),
                Label(
                    "Reminder (minutes)",
                    Input(type="number", name="reminder_minutes", value="15"),
                ),
                Label("Location", Input(name="location")),
                Label("FastMeet URL", Input(type="url", name="meet_url")),
                Label(
                    "Attendees",
                    Input(name="attendees", placeholder="name@example.com, …"),
                    cls="wide",
                ),
                Label(
                    "Recurrence",
                    Input(name="recurrence", placeholder="RRULE:FREQ=WEEKLY"),
                    cls="wide",
                ),
                Label(
                    "Description", Textarea(name="description", rows="4"), cls="wide"
                ),
                Button("Create event", cls="btn wide"),
                method="post",
                action="/events",
                cls="card",
            ),
        ),
    )


def booking_pages(identity: dict, rows: list[dict]):
    cards = [
        Article(
            H3(row["title"]),
            P(f"{row['duration_minutes']} minutes · {row['timezone']}"),
            A("Open public page", href=f"/book/{row['slug']}", target="_blank"),
            cls="event-row",
        )
        for row in rows
    ]
    return shell(
        identity,
        (
            Div(
                Span("SCHEDULING", cls="eyebrow"),
                H1("Booking pages"),
                P(
                    "Let customers and outside partners reserve available time without an account."
                ),
            ),
            Div(*cards, cls="events"),
            H2("Create booking page"),
            Form(
                Label("Meeting name", Input(name="title", required=True)),
                Label(
                    "Duration",
                    Select(
                        *[Option(f"{x} minutes", value=x) for x in (15, 30, 45, 60)],
                        name="duration_minutes",
                    ),
                ),
                Label(
                    "Available from",
                    Input(type="time", name="available_from", value="09:00"),
                ),
                Label(
                    "Available to",
                    Input(type="time", name="available_to", value="17:00"),
                ),
                Label("Time zone", Input(name="timezone", value="Europe/Tallinn")),
                Label(
                    "Minimum notice hours",
                    Input(type="number", name="minimum_notice_hours", value="4"),
                ),
                Label(
                    "Buffer minutes",
                    Input(type="number", name="buffer_minutes", value="10"),
                ),
                Label("Location or FastMeet link", Input(name="location")),
                Label(
                    "Description", Textarea(name="description", rows="3"), cls="wide"
                ),
                Button("Publish booking page", cls="btn wide"),
                method="post",
                action="/booking-pages",
                cls="card",
            ),
        ),
    )


def public_booking(page: dict, slots: list[dict], message: str = ""):
    return Html(
        Head(
            Title(f"Book {page['title']} · FastCal"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Style(CSS),
        ),
        Body(
            Nav(A("Fast", B("Cal"), href="/", cls="brand"), cls="nav"),
            Main(
                Section(
                    Div(
                        Span(page["organisation_name"].upper(), cls="eyebrow"),
                        H1(page["title"]),
                        P(
                            page["description"]
                            or f"Choose a time with {page['owner_name']}."
                        ),
                        P(f"{page['duration_minutes']} minutes · {page['timezone']}"),
                        P(message) if message else None,
                    ),
                    Form(
                        Label(
                            "Available time",
                            Select(
                                *[
                                    Option(
                                        s["label"],
                                        value=s["starts_at"],
                                        data_end=s["ends_at"],
                                    )
                                    for s in slots
                                ],
                                name="starts_at",
                                id="slot",
                            ),
                        ),
                        Input(
                            type="hidden",
                            name="ends_at",
                            id="slot-end",
                            value=slots[0]["ends_at"] if slots else "",
                        ),
                        Label("Your name", Input(name="guest_name", required=True)),
                        Label(
                            "Your email",
                            Input(type="email", name="guest_email", required=True),
                        ),
                        Label(
                            "Anything we should know?",
                            Textarea(name="guest_notes", rows="3"),
                            cls="wide",
                        ),
                        Button("Confirm booking", cls="btn wide", disabled=not slots),
                        Script(
                            "document.getElementById('slot')?.addEventListener('change',e=>document.getElementById('slot-end').value=e.target.selectedOptions[0].dataset.end)"
                        ),
                        method="post",
                        action=f"/book/{page['slug']}",
                        cls="card",
                    ),
                    cls="hero",
                )
            ),
        ),
    )
