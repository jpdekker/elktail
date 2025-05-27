import configparser
from elasticsearch import Elasticsearch
import warnings
from datetime import datetime

from elktail import configuration

# Suppress the specific Elasticsearch warning
warnings.filterwarnings('ignore', category=Warning)

def connect():
    config = configuration.get_config()
    return Elasticsearch(
        [config['host']],
        http_auth=(config['username'], config['password']),
        scheme=config['scheme'], port=config['port']
    )

def get_search_body(iso_date, process_name, severity, hostname, query_size=10000, sort_order="desc", query_string=None):
    # Basis query met timestamp filter
    must_conditions = [
        {"range": {"@timestamp": {"gte": iso_date}}}
    ]

    # Voeg process name filter toe indien opgegeven
    if process_name:
        must_conditions.append({"match": {"process.name": process_name}})

    # Voeg hostname filter toe indien opgegeven
    if hostname:
        must_conditions.append({"match": {"host.hostname": hostname}})

    # Voeg severity filter toe
    if severity:
        if isinstance(severity, list):
            # Voor een lijst van severities, gebruik terms query
            must_conditions.append({
                "terms": {
                    "log.syslog.severity.name": severity
                }
            })
        else:
            # Voor een enkele severity, gebruik match query
            must_conditions.append({
                "match": {
                    "log.syslog.severity.name": severity
                }
            })

    # Voeg query string toe indien opgegeven
    if query_string:
        must_conditions.append({"query_string": {"query": query_string}})

    # Bouw de complete query
    body = {
        "sort": [{"@timestamp": sort_order}],
        "size": query_size,
        "query": {
            "bool": {
                "must": must_conditions
            }
        }
    }

    return body

def search(es, body):
    return es.search(
        index=".ds-logs-syslog-default-*",
        body=body
    )

