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
        "slug": "network-consistency",
        "client": "Sydney Trains",
        "sector": "Transport & rail",
        "title": "The same standard, whatever the shift",
        "summary": "Holding one cleaning standard across stations that never really stop -- a quiet 3am platform and a packed peak-hour concourse get the same result.",
        "hero_image": "img/home/hero-platform.jpg",
        "outcome": "One fixed standard, held the same way on every shift",
        "challenge": (
            "Sydney Trains stations run around the clock, and conditions swing wildly -- a near-empty "
            "platform at 3am, a packed concourse at peak hour, weekday patterns nothing like the "
            "weekend. The risk with any contractor is the standard slipping when nobody's watching, "
            "or a busy shift becoming the excuse for a rushed job."
        ),
        "approach": [
            "A fixed scope for every shift, regardless of how quiet or busy the station is, so the job doesn't shrink to fit the time available.",
            "Crews rostered against each station's real traffic patterns, not a generic day-shift template, so the busiest hours get proper coverage.",
            "The same sign-on, sign-off and checklist process whether it's a Tuesday 3am shift or a Saturday peak -- nothing informal, nothing skipped.",
        ],
        "results": [
            "The same standard holds at 3am and at peak hour, not just when it's convenient",
            "Crews rostered around actual station traffic, not a one-size shift pattern",
            "A consistent sign-on/sign-off process that doesn't loosen under pressure",
        ],
        "narrative": (
            "Consistency is harder to prove than a one-off clean -- it isn't one shift going well, "
            "it's every shift going the same way, on the quiet nights and the packed afternoons alike. "
            "That's the actual job on a live network, and it's what the roster is built around."
        ),
    },
    {
        "slug": "hunter-line-restoration",
        "client": "Sydney Trains",
        "sector": "Transport & rail",
        "title": "Bringing a neglected line back to a standard worth using",
        "summary": "A stretch of the Hunter Line near Newcastle hadn't seen a proper clean in years -- algae, cobwebs and grime built up station after station. We took it back to a standard worth using.",
        "hero_image": "img/home/case-hunter-line.jpg",
        "outcome": "From years of neglect to a line worth using again",
        "challenge": (
            "A number of stations along the Hunter Line, near Newcastle, had gone without any real "
            "maintenance for a long stretch -- algae on platforms, cobwebs through shelters and "
            "walkways, surfaces that hadn't been properly cleaned in years. This wasn't a routine "
            "clean; it was a genuine restoration before daily servicing could even begin."
        ),
        "approach": [
            "Each station assessed individually first -- what had built up, where, and what it would actually take to shift it, rather than treating every platform the same.",
            "A dedicated deep-clean pass through every station on the stretch -- algae and grime removal, cobwebs cleared, surfaces brought back before any daily schedule could start.",
            "Once restored, each station moved onto the same ongoing service standard as the rest of the network, so the work didn't just reset the clock on the next round of neglect.",
        ],
        "results": [
            "Stations that hadn't been properly maintained in years brought back to a usable standard",
            "A one-off restoration pass followed through into an ongoing service schedule, not a one-time fix",
            "The same daily standard now applied here as anywhere else on the network",
        ],
        "narrative": (
            "Some jobs are about keeping a standard up. This one was about putting a standard there "
            "in the first place. The stretch along the Hunter Line went from platforms nobody wanted "
            "to stand on to stations that now look after themselves like everywhere else on the network."
        ),
    },
    {
        "slug": "sydney-cbd-interchanges",
        "client": "Sydney Trains",
        "sector": "Transport & rail",
        "title": "Deep cleaning Sydney's busiest interchanges",
        "summary": "Town Hall and Wynyard don't stop moving -- deep cleaning stations like these means working around a crowd that barely thins out.",
        "hero_image": "img/home/case-cbd-interchange.jpg",
        "outcome": "A full deep clean delivered without closing the platform",
        "challenge": (
            "Town Hall and Wynyard are two of the busiest interchanges in the network -- there's "
            "rarely a genuinely quiet window to work in. A deep clean here can't mean closing "
            "anything down; it has to happen around a crowd that barely thins out, without slowing "
            "anyone's commute."
        ),
        "approach": [
            "Work broken into sections and timed around the station's actual quieter windows, rather than one long shutdown-style clean.",
            "Crews briefed specifically for high-footfall interchange work -- moving around commuters safely, not working against them.",
            "A deep clean standard applied to the areas a routine daily pass doesn't always reach.",
        ],
        "results": [
            "A full deep clean delivered without closing the platform or disrupting commuters",
            "Crews trained specifically for high-footfall interchange conditions",
            "The areas a routine daily clean misses brought up to the same standard as everywhere else",
        ],
        "narrative": (
            "A quiet suburban platform and Town Hall at 5pm are not the same job. Interchanges like "
            "these needed a different approach -- not a lighter standard, just a smarter way of "
            "getting there around a crowd that never really stops."
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
    {
        "slug": "equipment-that-adapts",
        "client": "Every site",
        "sector": "Equipment & methodology",
        "title": "Equipment that adapts to the job, not the other way round",
        "summary": "Off-the-shelf equipment doesn't fit every site. We adjust kit and method based on what actually works on the ground, then carry it across every crew.",
        "hero_image": "img/home/case-equipment.jpg",
        "outcome": "Equipment and method shaped by what works on site, not a fixed catalogue",
        "challenge": (
            "Standard equipment doesn't automatically fit every site -- a method that works on a "
            "warehouse floor doesn't necessarily work on a live platform, and what a client actually "
            "needs isn't always what a generic setup provides. Sticking to a fixed kit regardless of "
            "the site was costing time and results."
        ),
        "approach": [
            "Equipment and technique reviewed against what each site and client actually needs, not assigned from a standard list.",
            "Crews given room to flag what isn't working on the ground, with changes tested and rolled out from there rather than left fixed indefinitely.",
            "Improvements that prove out on one site carried across other crews facing the same conditions, so the learning doesn't stay in one place.",
        ],
        "results": [
            "Equipment and method adjusted to the site instead of the site working around a fixed kit",
            "Changes driven by what crews see actually works, not assumptions made off-site",
            "Improvements from one site carried across others facing the same conditions",
        ],
        "narrative": (
            "The gear that gets the best result on one site isn't always right for the next one. "
            "Treating equipment and method as something to keep adjusting -- based on what crews and "
            "clients actually need -- has mattered more than any single piece of kit."
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
