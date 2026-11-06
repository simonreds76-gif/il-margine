"""Keep explicitly independent research failures separate from price delivery."""

# Default is operational/fail-closed. Do not classify by substring or fatal=False:
# real price, projection and settlement failures must still fail their parent.
RESEARCH_STEPS = {
    # Frozen candidate guard failures stay visible without failing live delivery.
    ('tennis_elo_shadow.py', 'Elo Rebuild paper comparison'),
    # Historical evidence collectors only. The separate live context rebuild,
    # current prices, projections and settlements remain operational/fail-closed.
    ('refresh-tennis-context-research.py', '0/6 Player context history (research only; live inputs unchanged)'),
    ('refresh-tennis-matchup-history.py', '0/6 Big-server and matchup histories (research only)'),
    ('tennis_sisal_5050.py', 'Freeze completed tournament evidence before Sisal quotes (paper only)'),
    ('tennis-most-aces-direct-live.py', 'tennis-most-aces-direct-live.py'),
}
RETIRED_UNATTENDED_SOURCES = {
    ('tennis-props-scrape-bet365-direct.py', 'Capture direct Bet365 service-break totals'),
}


def research_only(step):
    return (step.get('script'), step.get('label')) in RESEARCH_STEPS


def retired_research(step):
    # Exact retired capture only; settlement and all other research keep their guards.
    return (step.get('script'), step.get('label')) == ('tennis_elo_shadow.py', 'Elo Rebuild paper comparison')


def retired_source(step):
    return (step.get('script'), step.get('label')) in RETIRED_UNATTENDED_SOURCES
