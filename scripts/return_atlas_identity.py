"""Reviewed source aliases preserve already-published player URLs and history."""

# First present in the odds feed on 2026-09-25; matched to the existing
# OnCourt identities through full-name, fixture and result reconciliation.
PUBLISHED_ALIASES = {
    # 2021 extension: exact names, fixtures and results reconcile to these published IDs.
    '4174': '20463',  # Gianluca Mager
    '219': '791',  # Andreas Seppi
    '11556': '28685',  # Viktor Durasovic
    '1403': '22437',  # Nikola Milojevic
    '2152': '17359',  # Salvatore Caruso
    '119': '8721',  # Andrej Martin
    '15615': '46752',  # Kacper Zuk
    '244': '13820',  # Federico Gaio
    '912': '12495',  # Yuki Bhambri
    '1840': '12430',  # Prajnesh Gunneswaran
    '324': '13796',  # Cedrik-Marcel Stebe
    '125': '3492',  # Denis Istomin
    '130': '4454',  # Thomas Fabbiano
    '5315': '18648',  # Nicolas Kicker
    '1285': '12534',  # Renzo Olivo
    '10661': '34102',  # Lucas Catarina
    '357': '9521',  # Matthew Ebden
    '302': '7127',  # Thomaz Bellucci
    '13757': '33904',  # Raul Brancaccio

    '14507': '45197',  # Jie Cui
    '60351': '97973',  # Yi Zhou
}


def source_player_id(source_id, oncourt_id):
    source_id, oncourt_id = str(source_id), str(oncourt_id)
    expected = PUBLISHED_ALIASES.get(source_id)
    if expected is not None:
        if oncourt_id != expected:
            raise ValueError('Reviewed player alias disagrees with result identity')
        return 'oc-' + expected
    return 'vbt-' + source_id
