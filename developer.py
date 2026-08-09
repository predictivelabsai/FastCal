from fasthtml.common import *


def developer_page():
    return Title("FastCal API"), Main(
        H1("FastCal developer API"),
        P("Team event types, availability, slots, bookings and round-robin scheduling."),
        P(A("Swagger UI", href="/api/docs"), " · ", A("OpenAPI JSON", href="/swagger.json")),
        H2("Authentication"),
        P("FastOffice issues short-lived, audience-bound bearer grants for tenant access."),
        H2("Interoperability"),
        P("Google Calendar supplies external conflicts and destination events. FastMeet supplies meeting rooms."),
    )
