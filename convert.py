#!/usr/bin/env python3

import csv
import datetime
import errno
import json
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

class GeocodeCache:

    def __init__(self, cache_file_dir, cache_file_name='.geocode.cache', encoding='utf-8'):
        self.cache = {}
        self.cache_file_path = os.path.join(cache_file_dir, cache_file_name)
        self.encoding = encoding

    def load(self):
        if os.path.exists(self.cache_file_path):
            with open(self.cache_file_path, 'r', encoding=self.encoding) as fdcache:
                self.cache = json.load(fdcache)
            print(f'loaded geocode cache (N={len(self.cache)}) from {self.cache_file_path}')

    def save(self):
        with open(self.cache_file_path, 'w', encoding=self.encoding) as fdcache:
            json.dump(self.cache, fdcache)
        print(f'saved geocode cache (N={len(self.cache)}) in {self.cache_file_path}')

    def get(self, location):
        return self.cache.get(location)

    def set(self, location, value):
        self.cache[location] = value

def geocode(address, geocode_cache):

    if type(geocode_cache) is GeocodeCache:
        geocode = geocode_cache.get(address)
        if geocode is not None:
            return (geocode['lat'], geocode['lng'])

    wait = 12
    print(f'geocodes {address} after {wait} seconds ... ', end='', flush=True, file=sys.stderr)
    time.sleep(wait)

    text = get(address)
    if text is None:
        return (None, None)

    root = et.fromstring(text)
    coordinate = root.find('coordinate')
    if coordinate is None:
        error = str(root.find('error').text)
        print(f'error by remote api ({error})', file=sys.stderr)

        for i in range(1, 10):
            wait = wait + 10 * i
            print(f'geocodes again {address} after {wait} seconds ... ', end='', flush=True, file=sys.stderr)
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

    if type(geocode_cache) is GeocodeCache:
        geocode_cache.set(address, {
            'lat': lat,
            'lng': lng
        })

    return (lat, lng)

def get_year_and_month(month_expr):

    year = 0
    month = 0

    now_dt = datetime.datetime.now()
    if month_expr is None:
        month = now_dt.month
    elif re.match(r'^\d+$', month_expr):
        if len(month_expr) == 6:
            year = int(month_expr[:4])
            month = int(month_expr[4:])
        elif len(month_expr) == 4:
            year = int(month_expr[:2]) + (now_dt.year % 100)
            month = int(month_expr[2:])
        elif len(month_expr) > 0 and len(month_expr) < 3:
            month = int(month_expr)
        else:
            return None
    else:
        return None

    if int(month) - now_dt.month >= -3:
        year = now_dt.year
    else:
        year = now_dt.year + 1

    return [ year, month ]

def create_locations(data, month_expr, geocode_cache):

    month_vec = get_year_and_month(month_expr)
    if month_vec is None:
        return errno.EPERM

    year = month_vec[0]
    month = month_vec[1]
    day = 0

    locations = {}

    for original_row in data:
        inserting = True
        new_day = False

        if len(original_row) < 16:
            inserting = False
        else:
            date_expr = original_row[0]
            full_date_pattern = re.fullmatch(r'^(\d+)(\([日月火水木金土]\))$', date_expr)
            if full_date_pattern:
                day = int(full_date_pattern.group(1))
                new_day = True
            elif len(date_expr) > 0:
                inserting = False

        if inserting is True:

            name = re.sub('\s', '', ''.join(original_row[1:6]))
            dept = original_row[6]
            attr = re.sub('\s', '', original_row[7] + original_row[8])
            if attr == '○○':
                schedule = '昼間・準夜'
            elif attr == '○―':
                schedule = '昼間'
            elif attr == '―○':
                schedule = '準夜'
            elif attr == '――':
                schedule = '不明'
            address = re.sub('\s', '', ''.join(original_row[9:14]))
            tel = re.sub('\s', '', ''.join(original_row[14:]))

            (lat, lng) = geocode(address, geocode_cache)

            date_key = yymmdd(year, month, day)
            if date_key in locations:
                locations[yymmdd(year, month, day)].update({
                    f'{name}【{dept}】': {
                        'schedule': schedule,
                        'address': address,
                        'tel': tel,
                        'lat': lat,
                        'lng': lng
                    }
                })
            else:
                locations[date_key] = {
                    f'{name}【{dept}】': {
                        'schedule': schedule,
                        'address': address,
                        'tel': tel,
                        'lat': lat,
                        'lng': lng
                    }
                }
        else:
            line = re.sub('\s', '', ','.join(original_row))
            print(f'skipped [{line}]', file=sys.stderr)

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
            color_palette = [
                '#7f4500', '#008000', '#000080', '#b22222',
                '#ffdab9', '#00ff00', '#8a2be2', '#00ffff'
            ]
            color_index = 0
            for location_at_date in sorted(locations):
                entity_type = 'Date' + re.sub('-', '', location_at_date)
                print(f'{location_at_date},{tenant},{servicepath},{category},{entity_type},{color_palette[color_index % 8]},〇,location,time,名称,organization,0,1,住所,address,0,2,電話番号,tel,0,3,時間帯,schedule,0,4,,,,', file=fdp)
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
                color_index = color_index + 1

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
    parser.add_argument('--month', nargs=1, default=[None], help='year and month (ex. 202301, 2301 or 1)')
    parser.add_argument('--dir', nargs=1, metavar='DIR', default=['.'], help='working directory')
    parser.add_argument('--encoding', nargs=1, metavar='ENCODING', default=['utf-8'], help='encoding of source csv file')

    if len(sys.argv) < 2:
        print(parser.format_usage(), file=sys.stderr)
        return errno.EPERM

    args = parser.parse_args()

    geocode_cache = GeocodeCache(args.dir[0])
    geocode_cache.load()

    locations = create_locations(csv_to_matrix(args.meddent[0], args.dir[0], args.encoding[0]), args.month[0], geocode_cache)
    if type(locations) is int:
        return locations
    else:
        output(locations, args.dir[0])

    geocode_cache.save()

    return 0

if __name__ == '__main__':
    exit(main())
