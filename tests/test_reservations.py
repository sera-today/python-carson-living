# -*- coding: utf-8 -*-
"""Tests for observed Carson amenity reservation reads."""

import json
import requests_mock

from carson_living.const import (
    C_AMENITIES_ENDPOINT,
    C_AMENITY_ALLOWED_HOURS_ENDPOINT,
    C_AMENITY_RESERVATIONS_ENDPOINT,
    C_RESERVATIONS_API_URI,
)
from tests.helpers import load_fixture
from tests.test_base import CarsonUnitTestBase


class TestReservations(CarsonUnitTestBase):
    """Amenity reservation read API tests."""

    @requests_mock.Mocker()
    def test_list_amenities_uses_observed_v2_route(self, mock):
        """Amenity list uses the captured v2 route and filters."""
        fixture = load_fixture('carson.live', 'carson_amenities.json')
        mock.get(C_RESERVATIONS_API_URI + C_AMENITIES_ENDPOINT, text=fixture)
        client = self.carson.reservations_for(self.first_building.entity_id)
        result = client.list_amenities()
        self.assertEqual(1, result['count'])
        request = mock.last_request
        self.assertEqual(str(self.first_building.entity_id),
                         request.qs['building'][0])
        self.assertEqual('1', request.qs['active'][0])

    @requests_mock.Mocker()
    def test_list_reservations_uses_observed_filters(self, mock):
        """Reservation listing preserves captured status filters."""
        fixture = load_fixture('carson.live', 'carson_reservations.json')
        mock.get(C_RESERVATIONS_API_URI + C_AMENITY_RESERVATIONS_ENDPOINT,
                 text=fixture)
        client = self.carson.reservations_for(self.first_building.entity_id)
        result = client.list_reservations()
        self.assertEqual(1, result['count'])
        self.assertEqual('upcoming', mock.last_request.qs['status'][0])
        self.assertEqual('approved,denied,cancelled,pending',
                         mock.last_request.qs['approval_statuses'][0])

    @requests_mock.Mocker()
    def test_allowed_hours_accepts_observed_start_time_filter(self, mock):
        """Allowed-hours supports the captured optional start time."""
        endpoint = C_AMENITY_ALLOWED_HOURS_ENDPOINT.format(441)
        payload = json.dumps({
            'code': 0, 'status': 'OK', 'msg': None,
            'data': [{'startTime': '10:00:00', 'endTime': '11:00:00'}],
        })
        mock.get(C_RESERVATIONS_API_URI + endpoint, text=payload)
        client = self.carson.reservations_for(self.first_building.entity_id)
        result = client.allowed_hours(441, '2026-01-02', '10:00:00')
        self.assertEqual(1, len(result))
        self.assertEqual('2026-01-02', mock.last_request.qs['date'][0])
        self.assertEqual('10:00:00', mock.last_request.qs['start_time'][0])

    def test_requires_explicit_account_building(self):
        """Reservation clients cannot escape the account's buildings."""
        with self.assertRaises(ValueError):
            self.carson.reservations_for('not-associated')
