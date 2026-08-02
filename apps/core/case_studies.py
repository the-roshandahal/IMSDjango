"""Static case-study content for the public marketing site.

Not a model -- there's no admin workflow for these yet, so a plain list
is the right amount of machinery. If that changes, this is the seam to
promote into a CaseStudy model.
"""

CASE_STUDIES = [
    {
        "slug": "sydney-trains-network",
        "client": "Sydney Trains",
        "sector": "Transport & rail",
        "title": "Rolling daily cleaning out across a live network",
        "summary": "Extending scheduled cleaning and stock control across multiple stations without a single service disruption.",
        "hero_image": "img/home/hero-platform.jpg",
        "stat_value": "24",
        "stat_label": "stations onboarded",
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
            {"value": "24", "label": "Stations under daily service"},
            {"value": "0", "label": "Service disruptions caused"},
            {"value": "2019", "label": "Contract awarded"},
        ],
        "narrative": (
            "Five years on, the network relationship has grown from a handful of stations to "
            "two dozen, run on the same rostering and stock discipline that started the contract -- "
            "every shift signed on, every consumable tracked, every platform left the way it was found."
        ),
    },
    {
        "slug": "ubw-compliance",
        "client": "UBW",
        "sector": "Facilities & compliance",
        "title": "Bringing equipment compliance under one system",
        "summary": "Replacing paper test-and-tag records with a live compliance system across a multi-site facilities contract.",
        "hero_image": "img/home/service-fleet.jpg",
        "stat_value": "100%",
        "stat_label": "equipment under active test-and-tag",
        "challenge": (
            "UBW's facilities contract spanned several sites, each running its own paper test-and-tag "
            "register for electrical equipment. Expiries were easy to miss, and proving compliance at "
            "audit time meant chasing down whichever site held the paperwork that week."
        ),
        "approach": [
            "Every piece of equipment logged against the site it lives at, with a single expiry date tracked centrally.",
            "Vehicles brought into the same system alongside equipment, so service and insurance dates never slip through.",
            "Supervisors notified automatically ahead of an expiry, instead of finding out during an audit.",
        ],
        "results": [
            {"value": "100%", "label": "Equipment under active tracking"},
            {"value": "1", "label": "System of record, all sites"},
            {"value": "2022", "label": "Contract secured"},
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
        "stat_value": "12",
        "stat_label": "sites moved to a fixed schedule",
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
            {"value": "12", "label": "Sites on a fixed schedule"},
            {"value": "0", "label": "Reactive call-outs since rollout"},
        ],
        "narrative": (
            "The shift from reactive to scheduled didn't just tidy up the roster -- it gave the "
            "property manager a record they can point to, site by site, instead of taking a contractor's word for it."
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
