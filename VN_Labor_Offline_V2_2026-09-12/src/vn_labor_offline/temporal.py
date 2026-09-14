"""Instrument identity and conservative point-in-time eligibility (end exclusive)."""
from datetime import date
from .util import stable_id


def instrument_key(doc):
    # A consolidation needs an explicitly curated underlying instrument link.
    number=doc.get('instrument_number','')
    return number.upper() if number else 'UNRESOLVED:'+doc['document_id']


def instrument_id(doc):
    return stable_id(instrument_key(doc),prefix='instrument')


def temporal_eligible(record, query_date):
    """Unknown/unverified validity is excluded, rather than treated as always valid."""
    if not record.get('temporal_verified'):
        return False
    try:
        when=date.fromisoformat(str(query_date))
        start=date.fromisoformat(str(record['effective_from']))
        end=date.fromisoformat(str(record['effective_to'])) if record.get('effective_to') else None
    except (ValueError,KeyError):
        return False
    if record.get('version_role')=='CONSOLIDATED':
        try:
            if when<date.fromisoformat(str(record['consolidation_as_of'])): return False
        except (ValueError,KeyError): return False
    if record.get('status_checked_at') and not end:
        try:
            if when>date.fromisoformat(str(record['status_checked_at'])): return False
        except ValueError: return False
    # A present-day EXPIRED status does not invalidate queries before effective_to.
    if record.get('legal_status') not in {'EFFECTIVE','EXPIRED','PARTIALLY_EXPIRED'}:
        return False
    # A partially expired instrument still has provisions in force. Only a
    # fully expired instrument needs a whole-document end date here.
    if record.get('legal_status') == 'EXPIRED' and not end:
        return False
    return when>=start and (end is None or when<end)
