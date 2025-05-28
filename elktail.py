#!/usr/bin/env python

import os
import sys
import time
import errno
import warnings
import configparser
from datetime import datetime, timedelta
from optparse import OptionParser
from elasticsearch import Elasticsearch
from zoneinfo import ZoneInfo
import pytz

# Suppress Elasticsearch warnings
warnings.filterwarnings('ignore', category=Warning)

def get_config():
    """Get configuration from system or user config file."""
    system_config = '/etc/elktail.conf'
    user_config = os.path.join(os.environ.get("HOME"), ".elktail.conf")
    config_path = system_config if os.path.exists(system_config) else user_config

    if not os.path.exists(config_path):
        print("your elktail is not configured")
        opt = str(input("would you like to configure it now? <Y/n>: "))
        if opt.lower() in ['y', 'yes']:
            config_creator(config_path)
        sys.exit(-1)

    config = configparser.ConfigParser()
    config.read(config_path)
    return {
        'host': config['default']['host'],
        'username': config['default']['username'],
        'scheme': config['default']['scheme'],
        'password': config['default']['password'],
        'port': int(config['default']['port'])
    }

def config_creator(config_path):
    print(f"creating configuration file: {config_path}")
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    config = configparser.RawConfigParser()
    config.add_section("default")
    config.set("default", "host", input("elasticsearch host: "))
    config.set("default", "username", input("username: "))
    config.set("default", "password", input("password: "))
    config.set("default", "scheme", input("scheme (HIGHLY recommended https): "))
    config.set("default", "port", input("port: "))

    with open(config_path, 'w') as configfile:
        config.write(configfile)
    print("elktail configured")

def connect():
    config = get_config()
    return Elasticsearch(
        [config['host']],
        http_auth=(config['username'], config['password']),
        scheme=config['scheme'], 
        port=config['port']
    )

def get_search_body(iso_date, process_name, severity, hostname, query_size=10000, sort_order="desc", query_string=None):
    must_conditions = [
        {"range": {"@timestamp": {"gte": iso_date}}}
    ]

    if process_name:
        must_conditions.append({"match": {"process.name": process_name}})

    if hostname:
        must_conditions.append({"match": {"host.hostname": hostname}})

    if severity:
        if isinstance(severity, list):
            must_conditions.append({
                "terms": {"log.syslog.severity.name": severity}
            })
        else:
            must_conditions.append({
                "match": {"log.syslog.severity.name": severity}
            })

    if query_string:
        must_conditions.append({"query_string": {"query": query_string}})

    return {
        "sort": [{"@timestamp": sort_order}],
        "size": query_size,
        "query": {"bool": {"must": must_conditions}}
    }

def search(es, body):
    return es.search(
        index=".ds-logs-syslog-default-*",
        body=body
    )

def get_severity_level(severity_code):
    return {
        0: ('Emergency', 0),
        1: ('Alert', 0),
        2: ('Critical', 0),
        3: ('Error', 0),
        4: ('Warning', 0),
        5: ('Notice', 1),
        6: ('Informational', 1),
        7: ('Debug', 2),
    }.get(severity_code, ('Unknown', 2))

def get_lines(client, iso_date, process_name, severity, hostname, limit=None, verbosity=0, es_query_size=10000, es_sort_order="desc", query_string=None):
    last_timestamp = iso_date
    try:
        severity_levels = []
        if verbosity == 0:
            severity_levels = ["Emergency", "Alert", "Critical", "Error", "Warning"]
        elif verbosity == 1:
            severity_levels = ["Emergency", "Alert", "Critical", "Error", "Warning", "Notice", "Informational"]
        else:  # verbosity >= 2
            severity_levels = ["Emergency", "Alert", "Critical", "Error", "Warning", "Notice", "Informational", "Debug"]

        if severity:
            severity_levels = [severity]

        body = get_search_body(
            iso_date,
            process_name,
            severity_levels,
            hostname,
            query_size=es_query_size,
            sort_order=es_sort_order,
            query_string=query_string
        )
        if verbosity > 1:
            print(f"Elasticsearch query body: {body}")
        res = search(client, body)
        if verbosity > 1:
            print(f"Elasticsearch response: {res}")
    except Exception as e:
        if verbosity > 0:
            print(f"Error querying Elasticsearch: {e}")
        return last_timestamp, []

    lines_from_es = []
    for hit in res['hits']['hits']:
        try:
            timestamp_str = hit['_source']['@timestamp']
            message = hit['_source']['message'].strip()
            log_severity_name = hit['_source'].get('log', {}).get('syslog', {}).get('severity', {}).get('name', 'Unknown')
            log_hostname = hit['_source'].get('host', {}).get('hostname', 'Unknown')
            log_process_name = hit['_source'].get('process', {}).get('name', 'Unknown')
            
            dt_object = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            local_tz = pytz.timezone('Europe/Amsterdam')
            local_dt = dt_object.astimezone(local_tz)
            formatted_timestamp = local_dt.strftime('%b %d %H:%M:%S')

            severity_display = f" [{log_severity_name}]" if verbosity > 0 or log_severity_name in ["Error", "Warning", "Critical", "Alert", "Emergency"] else ""
            formatted_line = f"{formatted_timestamp} {log_hostname} {log_process_name}{severity_display}: {message}"

            lines_from_es.append({
                'timestamp_str': timestamp_str,
                'formatted_line': formatted_line
            })
        except KeyError as e:
            if verbosity > 0:
                print(f"Skipping hit due to missing key: {e} in hit: {hit}")
            continue
    
    if es_sort_order == "desc":
        lines_from_es.reverse()

    if limit is not None:
        final_lines = lines_from_es[-limit:]
    else:
        final_lines = lines_from_es

    if final_lines:
        last_timestamp = final_lines[-1]['timestamp_str']
    elif lines_from_es:
        last_timestamp = lines_from_es[-1]['timestamp_str']

    return last_timestamp, final_lines

def show_lines(lines):
    for line_data in lines:
        print(line_data['formatted_line'])

def mainloop(process_name=None, severity=None, hostname=None, follow=False, limit=10, verbosity=0, query_string=None, days=7):
    client = connect()
    
    if not follow:
        iso_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        es_query_size_non_follow = max(1000, limit * 10) if not any([process_name, severity, hostname, query_string]) else max(100, limit * 2)
        
        _, initial_lines = get_lines(
            client,
            iso_date,
            process_name,
            severity,
            hostname,
            limit=limit,
            verbosity=verbosity,
            es_query_size=es_query_size_non_follow,
            es_sort_order="desc",
            query_string=query_string
        )
        show_lines(initial_lines)
        return

    initial_iso_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    last_processed_timestamp, initial_lines = get_lines(
        client,
        initial_iso_date,
        process_name,
        severity,
        hostname,
        limit=limit,
        verbosity=verbosity,
        es_query_size=200,
        es_sort_order="asc",
        query_string=query_string
    )
    show_lines(initial_lines)

    processed_timestamps = set()
    for line in initial_lines:
        processed_timestamps.add(line['timestamp_str'])

    try:
        while True:
            last_timestamp, new_lines = get_lines(
                client,
                last_processed_timestamp,
                process_name,
                severity,
                hostname,
                limit=None,
                verbosity=verbosity,
                query_string=query_string
            )
            
            if new_lines:
                for line_data in new_lines:
                    if line_data['timestamp_str'] > last_processed_timestamp and \
                       line_data['timestamp_str'] not in processed_timestamps:
                        show_lines([line_data])
                        processed_timestamps.add(line_data['timestamp_str'])
                        if len(processed_timestamps) > 10000:
                            oldest = sorted(processed_timestamps)[:9000]
                            processed_timestamps = set(oldest)
                
                if new_lines[-1]['timestamp_str'] > last_processed_timestamp:
                    last_processed_timestamp = new_lines[-1]['timestamp_str']
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nExiting...")
        return

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-p", "--process", dest="process_name",
        help="filter by process name")
    parser.add_option("-s", "--severity", dest="severity",
        help="filter by log severity level (Emergency, Alert, Critical, Error, Warning, Notice, Informational, Debug)")
    parser.add_option("-H", "--hostname", dest="hostname",
        help="filter by hostname")
    parser.add_option("-q", "--query", dest="query_string",
        help="search for specific text in log messages")
    parser.add_option("-f", "--follow", dest="follow", action="store_true",
        help="follow log output (like tail -f)")
    parser.add_option("-n", "--lines", dest="limit", type="int", default=10,
        help="number of initial lines to show (default: 10)")
    parser.add_option("-d", "--days", dest="days", type="int", default=7,
        help="number of days to look back (default: 7)")
    parser.add_option("-v", "--verbose", dest="verbosity",
        action="count", default=0,
        help="increase output verbosity (-v shows Notice and Informational, -vv adds Debug)")
    
    args = sys.argv[1:]
    if len(args) > 0 and args[0].startswith('-') and args[0][1:].isdigit():
        number = int(args[0])
        args = args[1:]
        parser.set_defaults(limit=abs(number))
    
    (options, args) = parser.parse_args(args)

    mainloop(
        process_name=options.process_name,
        severity=options.severity,
        hostname=options.hostname,
        follow=options.follow,
        limit=options.limit,
        verbosity=options.verbosity,
        query_string=options.query_string,
        days=options.days
    )