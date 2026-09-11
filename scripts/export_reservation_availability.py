#!/usr/bin/env python3
"""Export a private, read-only Carson amenity availability snapshot."""

import argparse
import datetime
import json
import os
import time

import requests


ORIGIN = 'https://api.carson.live'
AUTH_ROOT = ORIGIN + '/api/v1.4.4'
API_ROOT = ORIGIN + '/api/v2.0.0'


def unwrap(response):
    """Validate Carson's response envelope and return its data."""
    response.raise_for_status()
    payload = response.json()
    if (payload.get('code') != 0 or payload.get('status') != 'OK' or
            'data' not in payload):
        raise RuntimeError('Carson returned an unexpected application result')
    return payload['data']


def get(session, path, params=None):
    """Perform a read-only v2 request."""
    response = session.get(API_ROOT + path, params=params, timeout=15,
                           allow_redirects=False)
    return unwrap(response)


def get_allowed_hours(session, amenity_id, date):
    """Return hours or a bounded provider error for an unavailable date."""
    response = session.get(
        API_ROOT + f'/amenities/{amenity_id}/allowed-hours/',
        params={'date': date}, timeout=15, allow_redirects=False)
    if response.status_code == 400:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        return {
            'available': False,
            'httpStatus': 400,
            'providerStatus': payload.get('status'),
            'providerCode': payload.get('code'),
        }
    return {'available': True, 'allowedHours': unwrap(response)}


def compact_amenity(item):
    """Retain non-personal amenity fields needed for scheduling."""
    keys = (
        'id', 'name', 'active', 'timezone', 'notes',
        'minimumDaysBeforeReservation', 'maximumDaysBeforeReservation',
        'minimumReservationTime', 'maximumReservationTime',
        'simultaneousNumberOfReservations', 'requiresApproval',
        'rentalAgreementRequired', 'schedule', 'reservationsCount',
        'reservationsCountPerWeek', 'reservationsCountPerMonth',
        'reservationsLeft', 'reservationsLeftPerWeek',
        'reservationsLeftPerMonth', 'upcomingReservationsCount',
    )
    return {key: item.get(key) for key in keys}


def compact_reservation(item):
    """Retain minimal reservation fields for authoritative readback."""
    status = item.get('status') or {}
    amenity = item.get('amenity') or {}
    return {
        'id': item.get('id'),
        'amenityId': amenity.get('id'),
        'amenityName': amenity.get('name'),
        'date': item.get('date'),
        'startTime': item.get('startTime'),
        'endTime': item.get('endTime'),
        'status': status.get('status'),
        'autoApproved': status.get('autoApprovedRequest'),
        'expired': item.get('expired'),
    }


def main():  # pylint: disable=too-many-locals,too-many-statements
    """Capture a bounded, private availability snapshot."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=14)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.days < 1 or args.days > 31:
        raise ValueError('--days must be between 1 and 31')

    username = os.environ.get('CARSON_USERNAME')
    password = os.environ.get('CARSON_PASSWORD')
    if not username or not password:
        raise RuntimeError('CARSON_USERNAME and CARSON_PASSWORD are required')

    session = requests.Session()
    session.headers.update({
        'Accept': 'application/json',
        'User-Agent': 'okhttp/4.9.0',
        'X-App-Version': '2.1.5',
        'X-Device-Type': 'android',
    })
    login = unwrap(session.post(
        AUTH_ROOT + '/auth/login/',
        json={'username': username, 'password': password},
        timeout=15, allow_redirects=False))
    session.headers['Authorization'] = 'JWT ' + login['token']
    account = unwrap(session.get(
        AUTH_ROOT + '/me/', timeout=15, allow_redirects=False))
    buildings = [item for item in account.get('properties', [])
                 if item.get('propertyLevel') == 'building']
    if len(buildings) != 1:
        raise RuntimeError('Expected exactly one explicitly selected building')
    building = buildings[0]
    building_id = building['id']

    amenities = []
    offset = 0
    while True:
        page = get(session, '/amenities/', {
            'active': 1, 'building': building_id,
            'limit': 20, 'offset': offset,
        })
        amenities.extend(page.get('results', []))
        if not page.get('next'):
            break
        offset += 20

    start_date = datetime.date.today()
    dates = [start_date + datetime.timedelta(days=delta)
             for delta in range(args.days)]
    spaces = []
    for amenity in amenities:
        amenity_id = amenity['id']
        detail = get(session, f'/amenities/{amenity_id}/')
        reserved = get(
            session, f'/amenities/{amenity_id}/reserved-dates/')
        availability = []
        minimum_days = int(
            detail.get('minimumDaysBeforeReservation') or 0)
        maximum_days = detail.get('maximumDaysBeforeReservation')
        if maximum_days is not None:
            maximum_days = int(maximum_days)
        for date in dates:
            day_offset = (date - start_date).days
            if day_offset < minimum_days:
                result = {'available': False,
                          'reason': 'before_minimum_advance_window'}
            elif (maximum_days is not None and
                  day_offset > maximum_days):
                result = {'available': False,
                          'reason': 'after_maximum_advance_window'}
            else:
                result = get_allowed_hours(
                    session, amenity_id, date.isoformat())
            result['date'] = date.isoformat()
            availability.append(result)
            time.sleep(0.05)
        spaces.append({
            'amenity': compact_amenity(detail),
            'reservedDates': reserved.get('reservedDates', []),
            'hasAvailableDates': reserved.get('hasAvailableDates'),
            'availability': availability,
        })

    reservations = get(session, '/amenities/reservations/', {
        'approval_statuses': 'approved,denied,cancelled,pending',
        'building': building_id, 'limit': 100, 'offset': 0,
        'status': 'upcoming',
    })
    snapshot = {
        'capturedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'building': {
            'id': building_id,
            'name': building.get('name'),
            'timezone': building.get('timezone'),
        },
        'horizonDays': args.days,
        'spaceCount': len(spaces),
        'spaces': spaces,
        'upcomingReservations': [compact_reservation(item) for item in
                                 reservations.get('results', [])],
    }
    output_dir = os.path.dirname(os.path.abspath(args.output))
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    with open(args.output, 'w', encoding='utf-8') as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write('\n')
    os.chmod(args.output, 0o600)
    print(json.dumps({
        'spaceCount': len(spaces),
        'horizonDays': args.days,
        'upcomingReservationCount': len(snapshot['upcomingReservations']),
        'output': os.path.abspath(args.output),
    }))


if __name__ == '__main__':
    main()
