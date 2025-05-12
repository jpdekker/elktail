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

def get_search_body(iso_date, process_name=None, severity=None, hostname=None, query_size=10000, sort_order="asc", query_string=None): # MODIFIED: Added query_string
    body = {
        "size": query_size,
        "sort": [
            {
                "@timestamp": {
                    "order": sort_order
                }
            }
        ],
        "query": {
            "bool": {
                "must": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": f"{iso_date}Z"
                            }
                        }
                    }
                ]
            }
        }
    }
    
    if hostname is not None:
        body['query']['bool']['must'].append(
            {
                'wildcard': {
                    'host.hostname': f"*{hostname}*"
                }
            }
        )
    
    if process_name is not None:
        body['query']['bool']['must'].append(
            {
                'term': {
                    'process.name': process_name
                }
            }
        )
    
    if severity is not None:
        body['query']['bool']['must'].append(
            {
                'match': {
                    'log.syslog.severity.name': severity
                }
            }
        )

    if query_string is not None: # ADDED: query_string filter
        body['query']['bool']['must'].append(
            {
                'match': {
                    'message': query_string
                }
            }
        )
    
    return body

def search(es, body):
    return es.search(
        index=".ds-logs-syslog-default-*",
        body=body
    )

