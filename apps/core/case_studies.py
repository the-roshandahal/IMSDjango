"""Static case-study content for the public marketing site.

Not a model -- there's no admin workflow for these yet, so a plain list
is the right amount of machinery. If that changes, this is the seam to
promote into a CaseStudy model.

Deliberately has no invented performance numbers (station counts, dates,
percentages) -- only Sydney Trains and UBW are real, named clients; the
rest are anonymised the same way a case study would be if the client
hadn't signed off on being named. "results" are qualitative outcomes,
not stats, for the same reason.
"""

CASE_STUDIES = [
    {
        "slug": "sydney-trains-network",
        "client": "Sydney Trains",
        "sector": "Transport & rail",
        "title": "Rolling daily cleaning out across a live network",
        "summary": "Extending scheduled cleaning and stock control across multiple stations without a single service disruption.",
        "hero_image": "img/home/hero-platform.jpg",
        "outcome": "From a handful of stations to network-wide coverage",
        "challenge": (
            "Sydney Trains needed a single contractor able to run consistent daily cleaning "
            "across multiple stations at once, each with its own platform access windows, "
            "crowd patterns and safety rules -- without slowing services or duplicating paperwork "
            "per site."
        ),
        "approach": [
            "RIW-certified crews rostered against each station's actual access windows, not a generic shift pattern.",
            "Consumables and equipment stock tracked per station, so a shortfall at one platform never stalls a shift.",
            "A shared audit trail across every site, so the client can see what was done, where, and by whom.",
        ],
        "results": [
            "Daily service extended station by station without disrupting a live network",
            "Rostering and stock discipline built once at the start has scaled cleanly as coverage grew",
            "One shared audit trail across every station, visible to the client any time",
        ],
        "narrative": (
            "The network relationship has grown from a handful of stations to a much larger footprint "
            "across the line, run on the same rostering and stock discipline that started the "
            "contract -- every shift signed on, every consumable tracked, every platform left the way "
            "it was found."
        ),
    },
    {
        "slug": "ubw-compliance",
        "client": "UBW",
        "sector": "Facilities & compliance",
        "title": "Bringing equipment compliance under one system",
        "summary": "Replacing paper test-and-tag records with a live compliance system across a multi-site facilities contract.",
        "hero_image": "img/home/service-fleet.jpg",
        "outcome": "From a paper register per site to one system of record",
        "challenge": (
            "UBW's facilities contract spanned several sites, each running its own paper test-and-tag "
            "register for electrical equipment. Expiries were easy to miss, and proving compliance at "
            "audit time meant chasing down whichever site held the paperwork that week."
        ),
        "approach": [
            "Every piece of equipment logged against the site it lives at, with a single expiry date tracked centrally.",
            "Vehicles brought into the same system alongside equipment, so service and insurance dates never slip through.",
            "Supervisors notified ahead of an expiry, instead of finding out during an audit.",
        ],
        "results": [
            "Every piece of equipment and every vehicle tracked in the same place",
            "One system of record across every site, not a folder per location",
            "Audit-ready on any given day, not just before an inspection",
        ],
        "narrative": (
            "What used to be a scramble before every audit is now a status a supervisor can check "
            "any morning -- equipment, vehicles and crew records all sitting against the same site record."
        ),
    },
    {
        "slug": "retail-deep-clean",
        "client": "A Western Sydney retail portfolio",
        "sector": "Retail & shopping centres",
        "title": "From reactive call-outs to a scheduled programme",
        "summary": "Turning an ad-hoc, call-when-needed arrangement into a scheduled deep clean programme with a clear record of every visit.",
        "hero_image": "img/home/service-spray.jpg",
        "outcome": "From call-when-needed to a fixed, trading-hours-aware schedule",
        "challenge": (
            "A retail portfolio had been calling in cleaning contractors reactively -- after a spill, "
            "a complaint, or a tenant request -- with no fixed schedule and no consistent record of what "
            "had actually been done at each centre."
        ),
        "approach": [
            "Each site moved onto a fixed deep clean schedule, planned around trading hours rather than complaints.",
            "Toolbox talks and crew attendance logged for every visit, so hours on site are never in question.",
            "A running record per site the property manager can check without having to ask.",
        ],
        "results": [
            "Every site moved onto a fixed, trading-hours-aware schedule",
            "Reactive, complaint-triggered call-outs replaced with planned visits",
            "A visit-by-visit record the property manager can check any time",
        ],
        "narrative": (
            "The shift from reactive to scheduled didn't just tidy up the roster -- it gave the "
            "property manager a record they can point to, site by site, instead of taking a contractor's word for it."
        ),
    },
    {
        "slug": "aged-care-infection-control",
        "client": "A Sydney aged care operator",
        "sector": "Healthcare & aged care",
        "title": "Lifting infection control from ad-hoc to routine",
        "summary": "Building a structured cleaning and disinfection routine for a residential aged care operator, with a clear record for every visit.",
        "hero_image": "img/home/service-ppe.jpg",
        "outcome": "From reactive outbreak response to a standing routine",
        "challenge": (
            "A residential aged care operator needed disinfection standards well above general "
            "commercial cleaning -- particularly for high-touch surfaces and communal areas -- but was "
            "relying on reactive call-outs whenever a concern came up, rather than a standing routine."
        ),
        "approach": [
            "A dedicated crew trained specifically for aged-care infection control, not general cleaning staff rotated in.",
            "Hospital-grade disinfection protocol applied to high-touch surfaces and communal areas on a fixed routine.",
            "A rapid-response protocol on standby for outbreak periods, on top of the standing schedule.",
        ],
        "results": [
            "A fixed disinfection routine in place of reactive, ad-hoc call-outs",
            "A dedicated crew trained specifically for aged-care infection control",
            "Visit records ready for compliance reporting, not assembled after the fact",
        ],
        "narrative": (
            "Infection control here isn't something that ramps up when there's a concern and quietly "
            "lapses afterwards -- it's the standing routine, with the outbreak response sitting on top "
            "of it rather than replacing it."
        ),
    },
]


def get_all_case_studies():
    return CASE_STUDIES


def get_case_study(slug):
    for case_study in CASE_STUDIES:
        if case_study["slug"] == slug:
            return case_study
    return None


def get_adjacent_case_studies(slug):
    """Returns (previous, next) case studies for the detail page's footer nav, wrapping around."""
    slugs = [c["slug"] for c in CASE_STUDIES]
    index = slugs.index(slug)
    prev_case_study = CASE_STUDIES[index - 1]
    next_case_study = CASE_STUDIES[(index + 1) % len(CASE_STUDIES)]
    return prev_case_study, next_case_study
