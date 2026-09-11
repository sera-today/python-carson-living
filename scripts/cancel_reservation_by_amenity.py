#!/usr/bin/env python3
"""Cancel one explicitly authorized upcoming reservation by amenity name."""

import argparse
import hashlib
import json
import os

from carson_living import CarsonAuth, CarsonReservations
from carson_living.const import C_API_URI, C_ME_ENDPOINT


def main():
    """Resolve exactly one matching reservation, cancel, and reconcile."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--amenity', required=True)
    parser.add_argument('--confirmed', action='store_true')
    args = parser.parse_args()
    if not args.confirmed:
        raise RuntimeError('--confirmed is required')

    username = os.environ.get('CARSON_USERNAME')
    password = os.environ.get('CARSON_PASSWORD')
    if not username or not password:
        raise RuntimeError('CARSON_USERNAME and CARSON_PASSWORD are required')

    auth = CarsonAuth(username, password)
    account = auth.authenticated_query(C_API_URI + C_ME_ENDPOINT)
    buildings = [item for item in account.get('properties', [])
                 if item.get('propertyLevel') == 'building']
    if len(buildings) != 1:
        raise RuntimeError('Expected exactly one explicitly selected building')
    client = CarsonReservations(auth, buildings[0]['id'])
    upcoming = client.list_reservations(limit=100).get('results', [])
    matches = [item for item in upcoming
               if (item.get('amenity') or {}).get('name') == args.amenity]
    if len(matches) != 1:
        raise RuntimeError(
            f'Expected exactly one upcoming reservation for amenity; found '
            f'{len(matches)}')

    target = matches[0]
    fingerprint = (f"{target.get('id')}|{target.get('date')}|"
                   f"{target.get('startTime')}|{target.get('endTime')}")
    operation_id = 'cancel-' + hashlib.sha256(
        fingerprint.encode('utf-8')).hexdigest()[:16]
    result = client.cancel_reservation(
        target['id'], operation_id=operation_id, confirmed=True)
    print(json.dumps({
        'amenity': args.amenity,
        'date': target.get('date'),
        'startTime': target.get('startTime'),
        'endTime': target.get('endTime'),
        'status': result.get('status'),
        'authoritativeReadback': True,
    }, sort_keys=True))


if __name__ == '__main__':
    main()
