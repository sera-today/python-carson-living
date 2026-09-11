# -*- coding: utf-8 -*-
"""Observed Carson amenity reservation API v2 read operations."""

from carson_living.const import (
    C_AMENITIES_ENDPOINT,
    C_AMENITY_ALLOWED_HOURS_ENDPOINT,
    C_AMENITY_ENDPOINT,
    C_AMENITY_RESERVATION_COUNTS_ENDPOINT,
    C_AMENITY_RESERVATIONS_ENDPOINT,
    C_AMENITY_RESERVED_DATES_ENDPOINT,
    C_RESERVATIONS_API_URI,
)


# pylint: disable=useless-object-inheritance
class CarsonReservations(object):
    """Read-only amenity reservation client for an explicit building."""

    def __init__(self, api, building_id):
        if building_id is None:
            raise ValueError('building_id is required')
        self._api = api
        self._building_id = building_id

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
