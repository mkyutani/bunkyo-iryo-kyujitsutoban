#!/usr/bin/env python3

import csv
import datetime
import errno
import os
import re
import requests
import sys
import time
import xml.etree.ElementTree as et

def yymmdd(y, m, d):
    return f'{int(y):04}-{int(m):02}-{int(d):02}'

def csv_to_matrix(csv_filename, dir, encoding='utf-8'):

    csv_path = os.path.join(dir, csv_filename)

    with open(csv_path, encoding=encoding) as fd:
        lines = fd.read()

    rows = csv.reader(lines.splitlines())
    matrix = []
    for row in rows:
        vec = []
        for c in row:
            str = re.sub('\s', ' ', c.translate(c.maketrans({chr(0xFF01 + i): chr(0x21 + i) for i in range(94)})))
            vec.append(str)
        if len(vec) == 0 or vec[0].startswith('#'):
            matrix.append([])
        else: 
            matrix.append(vec)

    return matrix

def get(address):

    uri = f'https://www.geocoding.jp/api/?q={address}'

    try:
        res = requests.get(uri)
    except requests.exceptions.RequestException as e:
        print(f'failed by requests ({e.response.text})', file=sys.stderr)
        return None
    except Exception as e:
        print(f'failed by general exception ({str(e)})', file=sys.stderr)
        return None

    if res.status_code >= 400:
        print(f'invalid status code from remote api ({res.status_code})', file=sys.stderr)
        return None
    elif res.text is None:
        print('no response from remote api', file=sys.stderr)
        return None

    return res.text

def geocode(address):

    wait = 12
    print(f'geocodes {address} after {wait} seconds ... ', end='', file=sys.stderr)
    time.sleep(wait)

    text = get(address)
    if text is None:
        return (None, None)

    root = et.fromstring(text)
    coordinate = root.find('coordinate')
    if coordinate is None:
        error = str(root.find('error').text)
        print(f'error by remote api ({error})', file=sys.stderr)

        for i in range(0, 10):
            wait = wait + 10 * i
            print(f'geocodes again {address} after {wait} seconds ... ', end='', file=sys.stderr)
            time.sleep(wait)

            text = get(address)
            if text is None:
                return (None, None)

            root = et.fromstring(text)
            coordinate = root.find('coordinate')
            if coordinate is None:
                error = str(root.find('error').text)
                print(f'error by remote api ({error})', file=sys.stderr)
            else:
                break
        else:
            return (None, None)

    lat = coordinate.find('lat').text
    lng = coordinate.find('lng').text

    print(f'{lat}, {lng}', file=sys.stderr)
    return (lat, lng)

def create_locations(data):

    locations = {}
    day = 0

    month_matched = re.match(r'^\d+', data[0][0])
    if month_matched is None:
        return errno.EIO
    month = int(month_matched.group())

    now_dt = datetime.datetime.now()
    if int(month) - now_dt.month >= -3:
        year = now_dt.year
    else:
        year = now_dt.year + 1

    locations_at_date = {}
    for original_row in data:
        inserting = True
        tag_line = False

        if len(original_row) < 12:
            inserting = False
        else:
            if re.fullmatch(r'\([日月火水木金土]\)', original_row[0]):
                tag_line = True
            elif re.fullmatch(r'\d+', original_row[0]):
                day = int(original_row[0])
            elif len(original_row[0]) == 0:
                pass
            else:
                inserting = False

            name = original_row[1]
            dept = original_row[2]
            attr = original_row[3] + original_row[4]
            if attr == '○○':
                schedule = '昼間・準夜'
            elif attr == '○―':
                schedule = '昼間'
            elif attr == '―○':
                schedule = '準夜'
            elif attr == '――':
                schedule = '不明'
            address = re.sub('\s', '', ''.join(original_row[5:11]))
            tel = original_row[11]

        if inserting is True:
            (lat, lng) = geocode(address)

            locations_at_date.update({
                f'{name}【{dept}】': {
                    'schedule': schedule,
                    'address': address,
                    'tel': tel,
                    'lat': lat,
                    'lng': lng
                }
            })
        else:
            line = re.sub('\s', '', ','.join(original_row))
            print(f'Skipped [{line}]', file=sys.stderr)

        if tag_line is True:
            locations.update({
                yymmdd(year, month, day): locations_at_date
            })
            locations_at_date = {}

    if len(locations_at_date) > 0:
        print('Some locations without schedule', file=sys.stderr)
        print(locations_at_date)
        return errno.EIO

    return locations

def output(locations, dir):

    tenant = 'bunkyo'
    servicepath = '/kyujitsuiryo'
    category = '当番医科歯科'

    now_string = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')

    point_path = os.path.join(dir, 'point.csv')
    point_data_path = os.path.join(dir, 'point_data.csv')

    with open(point_path, 'w') as fdp:
        with open(point_data_path, 'w') as fdpd:
            for location_at_date in sorted(locations):
                entity_type = 'Date' + re.sub('-', '', location_at_date)
                print(f'{location_at_date},{tenant},{servicepath},{category},{entity_type},#7f0000,〇,location,time,名称,organization,0,1,住所,address,0,2,電話番号,tel,0,3,時間帯,schedule,0,4,,,,', file=fdp)
                serial = 1
                for org in locations[location_at_date]:
                    location = locations[location_at_date][org]
                    address = location['address']
                    tel = location['tel']
                    schedule = location['schedule']
                    lat = location['lat']
                    lng = location['lng']
                    print(f'{entity_type}{serial:03},{tenant},{servicepath},{entity_type},organization,Text,{org}', file=fdpd)
                    print(f'{entity_type}{serial:03},{tenant},{servicepath},{entity_type},address,Text,{address}', file=fdpd)
                    print(f'{entity_type}{serial:03},{tenant},{servicepath},{entity_type},tel,Text,{tel}', file=fdpd)
                    print(f'{entity_type}{serial:03},{tenant},{servicepath},{entity_type},schedule,Text,{schedule}', file=fdpd)
                    print(f'{entity_type}{serial:03},{tenant},{servicepath},{entity_type},location,geo:point,"{lat}, {lng}"', file=fdpd)
                    print(f'{entity_type}{serial:03},{tenant},{servicepath},{entity_type},time,DateTime,{now_string}', file=fdpd)
                    serial = serial + 1

def main():

    import argparse
    from argparse import HelpFormatter
    from operator import attrgetter
    class SortingHelpFormatter(HelpFormatter):
        def add_arguments(self, actions):
            actions = sorted(actions, key=attrgetter('option_strings'))
            super(SortingHelpFormatter, self).add_arguments(actions)

    parser = argparse.ArgumentParser(description='make kyujitu iryo list of bunkyo city', formatter_class=SortingHelpFormatter)
    parser.add_argument('meddent', nargs=1, metavar='CSV', help='medical and dental schedule csv')
    parser.add_argument('-d', '--dir', nargs=1, metavar='DIR', default=['.'], help='working directory')
    parser.add_argument('--encoding', nargs=1, metavar='ENCODING', default=['utf-8'], help='encoding of source csv file')

    if len(sys.argv) < 2:
        print(parser.format_usage(), file=sys.stderr)
        return errno.EPERM

    args = parser.parse_args()

    locations = create_locations(csv_to_matrix(args.meddent[0], args.dir[0], args.encoding[0]))
    if type(locations) is int:
        return locations

    output(locations, args.dir[0])

    return 0

if __name__ == '__main__':
    exit(main())
