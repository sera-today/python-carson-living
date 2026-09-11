# -*- coding: utf-8 -*-
"""Observed Carson amenity reservation API v2 read operations."""

# Python 2.7 remains supported by the upstream project.
# pylint: disable=consider-using-f-string,raise-missing-from

from carson_living.const import (
    C_AMENITIES_ENDPOINT,
    C_AMENITY_ALLOWED_HOURS_ENDPOINT,
    C_AMENITY_CANCEL_RESERVATION_ENDPOINT,
    C_AMENITY_CREATE_RESERVATION_ENDPOINT,
    C_AMENITY_ENDPOINT,
    C_AMENITY_RESERVATION_COUNTS_ENDPOINT,
    C_AMENITY_RESERVATIONS_ENDPOINT,
    C_AMENITY_RESERVED_DATES_ENDPOINT,
    C_RESERVATIONS_API_URI,
)
from carson_living.error import (CarsonError,
                                 CarsonMutationApprovalError,
                                 CarsonUncertainMutationError)


def _no_content_handler(response):
    """Accept only the observed successful cancellation response."""
    if response.status_code != 204:
        raise CarsonUncertainMutationError(
            'Cancellation returned HTTP {}'.format(response.status_code))


# pylint: disable=useless-object-inheritance
class CarsonReservations(object):
    """Read-only amenity reservation client for an explicit building."""

    def __init__(self, api, building_id):
        if building_id is None:
            raise ValueError('building_id is required')
        self._api = api
        self._building_id = building_id
        self._operations = {}

    def list_amenities(self, limit=20, offset=0):
        """Return active amenities for the selected building."""
        return self._api.authenticated_query(
            C_RESERVATIONS_API_URI + C_AMENITIES_ENDPOINT,
            params={
                'active': 1,
                'building': self._building_id,
                'limit': limit,
                'offset': offset,
            })

    def get_amenity(self, amenity_id):
        """Return one amenity and its current reservation rules."""
        return self._api.authenticated_query(
            C_RESERVATIONS_API_URI +
            C_AMENITY_ENDPOINT.format(amenity_id))

    def reservation_counts(self):
        """Return past/upcoming reservation counts for the building."""
        return self._api.authenticated_query(
            C_RESERVATIONS_API_URI +
            C_AMENITY_RESERVATION_COUNTS_ENDPOINT,
            params={'building': self._building_id})

    def list_reservations(self, status='upcoming', limit=20, offset=0,
                          approval_statuses=None):
        """Return the resident's reservations for the selected building."""
        approval_statuses = approval_statuses or (
            'approved', 'denied', 'cancelled', 'pending')
        return self._api.authenticated_query(
            C_RESERVATIONS_API_URI + C_AMENITY_RESERVATIONS_ENDPOINT,
            params={
                'approval_statuses': ','.join(approval_statuses),
                'building': self._building_id,
                'limit': limit,
                'offset': offset,
                'status': status,
            })

    def reserved_dates(self, amenity_id):
        """Return dates that cannot accept another reservation."""
        return self._api.authenticated_query(
            C_RESERVATIONS_API_URI +
            C_AMENITY_RESERVED_DATES_ENDPOINT.format(amenity_id))

    def allowed_hours(self, amenity_id, date, start_time=None):
        """Return allowed hours on a local YYYY-MM-DD date."""
        params = {'date': date}
        if start_time is not None:
            params['start_time'] = start_time
        return self._api.authenticated_query(
            C_RESERVATIONS_API_URI +
            C_AMENITY_ALLOWED_HOURS_ENDPOINT.format(amenity_id),
            params=params)

    def _operation(self, operation_id, fingerprint):
        """Validate explicit approval and serialize duplicate intent."""
        if not operation_id:
            raise CarsonMutationApprovalError('operation_id is required')
        previous = self._operations.get(operation_id)
        if previous and previous['fingerprint'] != fingerprint:
            raise CarsonMutationApprovalError(
                'operation_id was already used for different intent')
        return previous

    def _remember(self, operation_id, fingerprint, result):
        self._operations[operation_id] = {
            'fingerprint': fingerprint,
            'result': result,
        }
        return result

    # pylint: disable=too-many-positional-arguments
    def create_reservation(self, amenity_id, date, start_time, end_time,
                           operation_id=None, confirmed=False):
        """Create one explicitly confirmed reservation and reconcile it."""
        if not confirmed:
            raise CarsonMutationApprovalError(
                'Explicit confirmation is required to create a reservation')
        fingerprint = ('create', amenity_id, date, start_time, end_time)
        previous = self._operation(operation_id, fingerprint)
        if previous:
            return previous['result']

        # Recheck current availability immediately before the mutation.
        available = self.allowed_hours(amenity_id, date, start_time)
        if not available:
            raise CarsonMutationApprovalError(
                'Requested start time is no longer available')

        payload = {
            'date': date,
            'startTime': start_time,
            'endTime': end_time,
        }
        try:
            result = self._api.authenticated_query(
                C_RESERVATIONS_API_URI +
                C_AMENITY_CREATE_RESERVATION_ENDPOINT.format(amenity_id),
                method='post', json=payload, retry_auth=0)
        except CarsonError:
            result = self._find_reservation(
                amenity_id, date, start_time, end_time)
            if result is None:
                raise CarsonUncertainMutationError(
                    'Create result is uncertain; do not submit again')

        reservation_id = result.get('id') if result else None
        verified = self._find_reservation(
            amenity_id, date, start_time, end_time)
        if verified is None or verified.get('id') != reservation_id:
            raise CarsonUncertainMutationError(
                'Created reservation was not found in authoritative listing')
        return self._remember(operation_id, fingerprint, verified)

    def cancel_reservation(self, reservation_id, operation_id=None,
                           confirmed=False):
        """Cancel one explicitly confirmed reservation and reconcile it."""
        if not confirmed:
            raise CarsonMutationApprovalError(
                'Explicit confirmation is required to cancel a reservation')
        fingerprint = ('cancel', reservation_id)
        previous = self._operation(operation_id, fingerprint)
        if previous:
            return previous['result']

        if self._find_reservation_by_id(reservation_id) is None:
            raise CarsonMutationApprovalError(
                'Reservation is not present in the authoritative listing')
        try:
            self._api.authenticated_query(
                C_RESERVATIONS_API_URI +
                C_AMENITY_CANCEL_RESERVATION_ENDPOINT.format(reservation_id),
                method='delete', retry_auth=0,
                response_handler=_no_content_handler)
        except CarsonError:
            if self._find_reservation_by_id(reservation_id) is not None:
                raise CarsonUncertainMutationError(
                    'Cancel result is uncertain; do not submit again')

        if self._find_reservation_by_id(reservation_id) is not None:
            raise CarsonUncertainMutationError(
                'Cancelled reservation remains in authoritative listing')
        result = {'id': reservation_id, 'status': 'cancelled'}
        return self._remember(operation_id, fingerprint, result)

    def _find_reservation(self, amenity_id, date, start_time, end_time):
        data = self.list_reservations()
        for reservation in data.get('results', []):
            amenity = reservation.get('amenity') or {}
            if (amenity.get('id') == amenity_id and
                    reservation.get('date') == date and
                    reservation.get('startTime') == start_time and
                    reservation.get('endTime') == end_time):
                return reservation
        return None

    def _find_reservation_by_id(self, reservation_id):
        data = self.list_reservations()
        for reservation in data.get('results', []):
            if reservation.get('id') == reservation_id:
                return reservation
        return None
