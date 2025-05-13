#!/usr/bin/env python

import sys
import time
from datetime import datetime, timedelta
from optparse import OptionParser
import json
from zoneinfo import ZoneInfo  # For Python 3.9+
import pytz # ADDED: Import pytz

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

# NEW HELPER FUNCTION
def get_filter_level_for_severity_name(severity_name):
    """Maps severity name to a numeric filter level."""
    # Level 0: Always shown (Emergency, Alert, Critical, Error, Warning)
    # Level 1: Shown with -v (Notice, Informational)
    # Level 2: Shown with -vv (Debug)
    mapping = {
        'Emergency': 0,
        'Alert': 0,
        'Critical': 0,
        'Error': 0,
        'Warning': 0,
        'Notice': 1,
        'Informational': 1,
        'Debug': 2,
    }
    return mapping.get(severity_name, 0) # Default to 0 (most important) if name is unknown

# MODIFIED: Added es_query_size and es_sort_order parameters
def get_lines(client, iso_date, process_name, severity, hostname, limit=None, verbosity=0, es_query_size=10000, es_sort_order="desc", query_string=None): # MODIFIED: Default es_sort_order to "desc"
    last_timestamp = iso_date # Default last_timestamp to the start of the query window
    try:
        body = elastic.get_search_body(
            iso_date,
            process_name,
            severity,
            hostname,
            query_size=es_query_size,
            sort_order=es_sort_order,
            query_string=query_string
        )
        if verbosity > 1:
            print(f"Elasticsearch query body: {body}")
        res = elastic.search(client, body)
        if verbosity > 1:
            print(f"Elasticsearch response: {res}")
    except Exception as e:
        if verbosity > 0:
            print(f"Error querying Elasticsearch: {e}")
        return last_timestamp, []

    lines_from_es = []
    duplicate_timestamps_in_batch = set()

    for hit in res['hits']['hits']:
        try:
            timestamp_str = hit['_source']['@timestamp']
            message = hit['_source']['message'].strip()
            log_severity_name = hit['_source'].get('log', {}).get('syslog', {}).get('severity', {}).get('name', 'Unknown')
            log_hostname = hit['_source'].get('host', {}).get('hostname', 'Unknown')
            log_process_name = hit['_source'].get('process', {}).get('name', 'Unknown')

            if timestamp_str in duplicate_timestamps_in_batch:
                if verbosity > 1: print(f"Skipping duplicate timestamp within batch: {timestamp_str}")
                continue
            duplicate_timestamps_in_batch.add(timestamp_str)
            
            # Simply convert the timestamp directly - no manual Z manipulation needed
            dt_object = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            local_tz = pytz.timezone('Europe/Amsterdam')
            local_dt = dt_object.astimezone(local_tz)
            formatted_timestamp = local_dt.strftime('%b %d %H:%M:%S')

            # Severity display tag logic remains the same (controls [TAG] visibility)
            severity_display = f" [{log_severity_name}]" if verbosity > 0 or log_severity_name in ["Error", "Warning", "Critical", "Alert", "Emergency"] else ""
            
            formatted_line = f"{formatted_timestamp} {log_hostname} {log_process_name}{severity_display}: {message}"
            
            # Get the numeric filter level for this log's severity
            current_log_filter_level = get_filter_level_for_severity_name(log_severity_name)

            lines_from_es.append({
                'timestamp_str': timestamp_str,
                'formatted_line': formatted_line,
                'severity_name': log_severity_name, # Keep original name for display logic
                'filter_level': current_log_filter_level # Store its filter level
            })
        except KeyError as e:
            if verbosity > 0:
                print(f"Skipping hit due to missing key: {e} in hit: {hit}")
            continue
    
    # Ensure lines_from_es is chronological if fetched in descending order
    if es_sort_order == "desc":
        lines_from_es.reverse() # Now chronological (oldest of batch to newest of batch)

    # Filter lines based on verbosity BEFORE applying the limit
    filtered_by_verbosity_lines = []
    for line_data in lines_from_es:
        log_filter_level = line_data['filter_level']
        if verbosity == 0: # No -v flag
            if log_filter_level == 0:
                filtered_by_verbosity_lines.append(line_data)
        elif verbosity == 1: # -v flag
            if log_filter_level <= 1:
                filtered_by_verbosity_lines.append(line_data)
        elif verbosity >= 2: # -vv or more
            filtered_by_verbosity_lines.append(line_data) # Show all

    # Apply limit if specified to the verbosity-filtered lines
    if limit is not None:
        final_lines_to_return = filtered_by_verbosity_lines[-limit:]
    else:
        final_lines_to_return = filtered_by_verbosity_lines

    # Determine last_timestamp from the actual lines being returned
    if final_lines_to_return:
        last_timestamp = final_lines_to_return[-1]['timestamp_str']
    elif filtered_by_verbosity_lines: # If limit made final_lines_to_return empty, but filtered list had lines
        last_timestamp = filtered_by_verbosity_lines[-1]['timestamp_str']
    elif lines_from_es: # If verbosity filter removed all lines, but original fetch had lines
        last_timestamp = lines_from_es[-1]['timestamp_str']
    # else, last_timestamp remains iso_date (initial value)

    return last_timestamp, final_lines_to_return

def show_lines(lines):
    for line_data in lines: # MODIFIED: iterate through line_data (dictionaries)
        print(line_data['formatted_line']) # MODIFIED: print the 'formatted_line'


def mainloop(process_name=None, severity=None, hostname=None, follow=False, limit=10, verbosity=0, query_string=None, days=7):
    client = elastic.connect()
    
    if not follow:
        # Non-follow mode:
        iso_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        # Fetch more than 'limit' from ES to be robust, then take the newest 'limit' lines.
        # This helps if ES behaves unexpectedly with very small 'size' requests.
        es_query_size_non_follow = max(100, limit * 2) # Ensure we ask for a decent chunk
        
        _, initial_lines = get_lines(
            client,
            iso_date,
            process_name,
            severity,
            hostname,
            limit=limit,  # Apply the desired limit *after* fetching a larger batch
            verbosity=verbosity,
            es_query_size=es_query_size_non_follow, # How many to get from ES
            es_sort_order="desc", # Fetch newest first from ES
            query_string=query_string
        )
        show_lines(initial_lines)
        return

    # Follow mode:
    initial_iso_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    # For initial fetch in follow mode, get 'limit' lines, ask ES for a moderate batch.
    last_processed_timestamp, initial_lines = get_lines(
        client,
        initial_iso_date,
        process_name,
        severity,
        hostname,
        limit=limit, # We want to display 'limit' lines initially
        verbosity=verbosity,
        es_query_size=200, # Fetch a moderate batch from ES
        es_sort_order="asc", # Fetch oldest first for scanning history
        query_string=query_string
    )
    show_lines(initial_lines)

    processed_timestamps = set(line['timestamp_str'] for line in initial_lines)
    # last_processed_timestamp is now correctly the timestamp of the newest displayed line
    last_processed_timestamp_for_filtering = last_processed_timestamp 

    # Initialize variables for follow mode
    now = datetime.now(ZoneInfo('UTC'))
    last_processed_timestamp = now.isoformat()
    processed_timestamps = set()  # Track all processed timestamps
    display_lines = []  # Keep track of displayed lines
    
    try:
        while True:
            last_timestamp, new_lines = get_lines(
                client,
                last_processed_timestamp,
                process_name,
                severity,
                hostname,
                limit=None,  # Don't limit in get_lines for follow mode
                verbosity=verbosity,
                query_string=query_string
            )
            
            if new_lines:
                # Process new lines and avoid duplicates
                for line_data in new_lines:
                    if line_data['timestamp_str'] > last_processed_timestamp and \
                       line_data['timestamp_str'] not in processed_timestamps:
                        show_lines([line_data])
                        processed_timestamps.add(line_data['timestamp_str'])
                        display_lines.append(line_data)
                        # Keep the set size manageable
                        if len(processed_timestamps) > 10000:
                            processed_timestamps.clear()
                            processed_timestamps.update(line['timestamp_str'] for line in display_lines[-1000:])
                
                # Update the timestamp for next query
                if new_lines[-1]['timestamp_str'] > last_processed_timestamp:
                    last_processed_timestamp = new_lines[-1]['timestamp_str']
            
            time.sleep(0.1)  # Small delay to prevent hammering the server
            
    except KeyboardInterrupt:
        print("\nExiting...")
        return

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
    parser.add_option("-d", "--days", dest="days", type="int", default=7,
        help="number of days to look back (default: 7)")
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
        query_string=options.query_string,
        days=options.days
    )
