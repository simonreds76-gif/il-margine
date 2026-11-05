"""Keep explicitly independent research failures separate from price delivery."""

# Default is operational/fail-closed. Do not classify by substring or fatal=False:
# real price, projection and settlement failures must still fail their parent.
RESEARCH_STEPS = {
    ('tennis_sisal_5050.py', 'Freeze completed tournament evidence before Sisal quotes (paper only)'),
    ('tennis-most-aces-direct-live.py', 'tennis-most-aces-direct-live.py'),
}
RETIRED_UNATTENDED_SOURCES = {
    ('tennis-props-scrape-bet365-direct.py', 'Capture direct Bet365 service-break totals'),
}


def research_only(step):
    return (step.get('script'), step.get('label')) in RESEARCH_STEPS


def retired_source(step):
    return (step.get('script'), step.get('label')) in RETIRED_UNATTENDED_SOURCES
