from fasthtml.common import *


def developer_page():
    return Title("FastCal API"), Main(
        H1("FastCal developer API"),
        P("Tenant-scoped access to calendars, events, booking pages and availability."),
        P(A("Swagger UI", href="/api/docs"), " · ", A("OpenAPI JSON", href="/swagger.json")),
        H2("Authentication"),
        P("FastOffice issues short-lived audience-bound bearer grants. FASTSME_API_TOKEN is not used for tenant access."),
        H2("Interoperability"),
        P("Optional Cal.com and Calendly adapters map event types, availability, slots and bookings while FastCal remains the source of truth."),
    )
