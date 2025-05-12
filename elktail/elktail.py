#!/usr/bin/env python

import sys
import time
from datetime import datetime, timedelta
from optparse import OptionParser
import json
from zoneinfo import ZoneInfo  # For Python 3.9+

from elktail import elastic

def get_severity_level(severity_code):
    # Syslog severity levels (RFC 5424)
    # Lower numbers are more severe
    return {
        0: ('Emergency', 0),    # System is unusable
        1: ('Alert', 0),        # Action must be taken immediately
        2: ('Critical', 0),     # Critical conditions
        3: ('Error', 0),        # Error conditions
        4: ('Warning', 0),      # Warning conditions (Changed from 1 to 0)
        5: ('Notice', 1),       # Normal but significant conditions
        6: ('Informational', 1),# Informational messages (Changed from 2 to 1)
        7: ('Debug', 2),        # Debug-level messages
    }.get(severity_code, ('Unknown', 2))

# MODIFIED: Added es_query_size and es_sort_order parameters
def get_lines(client, iso_date, process_name=None, severity=None, hostname=None, limit=None, verbosity=0, es_query_size=10000, es_sort_order="asc", query_string=None): 
    # MODIFIED: Pass query_size, sort_order, and query_string to elastic.get_search_body
    body = elastic.get_search_body(iso_date, process_name, severity, hostname, query_size=es_query_size, sort_order=es_sort_order, query_string=query_string)
    response = elastic.search(client, body)
    new_ts = None 
    lines = list()
    seen_entries = set()

    processed_docs = response['hits']['hits']

    for doc in processed_docs:
        source = doc['_source']
        
        host = source.get('host', {}).get('hostname', 'unknown')
        process = source.get('process', {}).get('name', 'unknown')
        pid = source.get('process', {}).get('pid', '')
        severity_code = source.get('log', {}).get('syslog', {}).get('severity', {}).get('code', 6)
        severity_name = source.get('log', {}).get('syslog', {}).get('severity', {}).get('name', 'unknown')
        message = source.get('message', '').strip()
        
        msg_severity_name, msg_verbosity = get_severity_level(severity_code)
        if msg_verbosity > verbosity:
            continue
        
        utc_time = datetime.strptime(source['@timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")
        
        entry_id = f"{utc_time.isoformat()}:{message}"
        if entry_id in seen_entries:
            continue
        seen_entries.add(entry_id)
        
        local_time = utc_time.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Europe/Amsterdam'))
        ts = local_time.strftime("%b %d %H:%M:%S")
        
        process_info = f"{process}[{pid}]" if pid else process
        
        log_line = f"{ts} {host} {process_info} [{severity_name}]: {message}"
            
        lines.append(log_line.rstrip())
        
        # This new_ts is primarily for follow mode, which uses 'asc' sort.
        # It correctly takes the timestamp of the last processed document in that case.
        current_doc_ts_for_new_ts = utc_time + timedelta(milliseconds=1)
        new_ts = current_doc_ts_for_new_ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

    # MODIFIED: If ES returned newest first, reverse to make lines chronological.
    if es_sort_order == "desc":
        lines.reverse() 

    # MODIFIED: Apply display limit, typically for follow mode's initial fetch
    # when a larger batch was fetched ('asc' order) than what needs to be displayed.
    if limit and len(lines) > limit and es_sort_order == "asc":
        lines = lines[-limit:]

    return new_ts, lines


def show_lines(lines):
    for line in lines:
        print(line)


def mainloop(process_name=None, severity=None, hostname=None, follow=False, limit=10, verbosity=0, query_string=None): # MODIFIED: Added query_string
    client = elastic.connect()
    
    if not follow:
        # Non-follow mode:
        iso_date = (datetime.utcnow() - timedelta(days=7)).isoformat()
        # Fetch 'limit' newest lines from ES. get_lines will reverse them for chronological display.
        _, initial_lines = get_lines(
            client,
            iso_date,
            process_name,
            severity,
            hostname,
            limit=None,  # Display limit is handled by es_query_size for 'desc' sort
            verbosity=verbosity,
            es_query_size=limit, # Ask ES for exactly 'limit' lines
            es_sort_order="desc", # Ask ES for newest first
            query_string=query_string # MODIFIED: Pass query_string
        )
        show_lines(initial_lines)
        return

    # Follow mode:
    # Initial fetch for follow mode:
    initial_iso_date = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    # Fetch a larger batch (e.g., 200 lines) sorted 'asc'.
    # get_lines will then take the last 'limit' lines from this batch for display.
    last_processed_timestamp, initial_lines = get_lines(
        client,
        initial_iso_date,
        process_name,
        severity,
        hostname,
        limit=limit, # The number of lines to display initially
        verbosity=verbosity,
        es_query_size=200, # Fetch a larger batch to pick from
        es_sort_order="asc", # Oldest first
        query_string=query_string # MODIFIED: Pass query_string
    )
    show_lines(initial_lines)
    
    next_query_start_time = last_processed_timestamp

    # Follow mode - streaming new entries:
    while True:
        time.sleep(2)
        
        if next_query_start_time is None:
            next_query_start_time = (datetime.utcnow() - timedelta(seconds=10)).isoformat()
        
        current_timestamp, new_lines = get_lines(
            client,
            next_query_start_time,
            process_name,
            severity,
            hostname,
            limit=None, # No display limit for streaming part, show all new lines
            verbosity=verbosity,
            es_query_size=10000, # Default large size for streaming
            es_sort_order="asc", # Always 'asc' for follow streaming
            query_string=query_string # MODIFIED: Pass query_string
        )
        
        if new_lines:
            show_lines(new_lines)
            next_query_start_time = current_timestamp
        elif current_timestamp: # No new lines, but ES query might have advanced the effective time
             next_query_start_time = current_timestamp


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
    parser.add_option("-v", "--verbose", dest="verbosity",
        action="count", default=0,
        help="increase output verbosity (-v shows Notice and Informational, -vv adds Debug)")
    
    # Handle negative numbers for lines
    args = sys.argv[1:]
    if len(args) > 0 and args[0].startswith('-') and args[0][1:].isdigit():
        number = int(args[0])
        args = args[1:]  # Remove the number argument
        parser.set_defaults(limit=abs(number))  # Use absolute value of the number
    
    (options, args) = parser.parse_args(args)

    mainloop(
       process_name=options.process_name,
       severity=options.severity,
       hostname=options.hostname,
       follow=options.follow,
       limit=options.limit,
       verbosity=options.verbosity,
       query_string=options.query_string # MODIFIED: Pass query_string
    )
