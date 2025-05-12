# ELKTAIL

## Description

ELKTAIL is a tool that generates a tail-like stream from a filebeat index
in elasticsearch.

Currently it depends that the the index template has the following fields:

* fields.project.keyword
* fields.process_type.keyword
* fields.environment.keyword

**Future versions:** Won't have this requirement since it will allow KQL 
language directly.

## Installation

The tools gets installed globally on your system so it requires root
permissions. Its final destination will be /usr/local/elktail.

### Download the latest release

* [1.0](https://github.com/BridgeMarketing/elktail/releases/tag/v1.0)

### Clone the project

```bash
$ git clone git@github.com:BridgeMarketing/elktail.git
$ cd elktail/
$ sudo python setup.py install
running install
running build
running build_py
copying elktail/elktail.py -> build/lib/elktail
copying elktail/create_bin.py -> build/lib/elktail
copying elktail/configuration.py -> build/lib/elktail
copying elktail/elastic.py -> build/lib/elktail
copying elktail/__init__.py -> build/lib/elktail
running install_lib
copying build/lib/elktail/elktail.py -> /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail
copying build/lib/elktail/create_bin.py -> /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail
copying build/lib/elktail/configuration.py -> /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail
copying build/lib/elktail/elastic.py -> /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail
copying build/lib/elktail/__init__.py -> /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail
byte-compiling /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail/elktail.py to elktail.cpython-37.pyc
byte-compiling /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail/create_bin.py to create_bin.cpython-37.pyc
byte-compiling /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail/configuration.py to configuration.cpython-37.pyc
byte-compiling /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail/elastic.py to elastic.cpython-37.pyc
byte-compiling /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail/__init__.py to __init__.cpython-37.pyc
running install_egg_info
running egg_info
writing elktail.egg-info/PKG-INFO
writing dependency_links to elktail.egg-info/dependency_links.txt
writing top-level names to elktail.egg-info/top_level.txt
reading manifest file 'elktail.egg-info/SOURCES.txt'
writing manifest file 'elktail.egg-info/SOURCES.txt'
Copying elktail.egg-info to /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail-0.3-py3.7.egg-info
Running post install task. Generating exec
/home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages/elktail
Copying binaries
Requirement already satisfied: elasticsearch==7.7.1 in /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages (from -r etc/requirements.txt (line 1)) (7.7.1)
Requirement already satisfied: urllib3>=1.21.1 in /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages (from elasticsearch==7.7.1->-r etc/requirements.txt (line 1)) (1.25.9)
Requirement already satisfied: certifi in /home/username/.pyenv/versions/3.7.7/lib/python3.7/site-packages (from elasticsearch==7.7.1->-r etc/requirements.txt (line 1)) (2020.4.5.1)
```

## Configuration

The first time this tool gets executed (or if the configuration file is
missing) the initial configuration process kicks in. The following
parameters will be requested:

* host: url or ip of the elasticsearch that contains the filebeat indexes
* username: user that has permissions to connect to the given elasticsearch
* password: password of the username
* scheme: it's really REALLY weird the this parameter be anything by https
* port: port where elasticsearch is listening

```bash
$ elktail
your elktail is not configured
would you like to configure it now? <Y/n>: y
creating configuration file: /home/username/.config/elktail/config.ini
elasticsearch host: 127.0.0.1
username: username
password: MySecretPassword
scheme (HIGLY recommended https): https
port: 9243
elktail configured
$ cat $HOME/.config/elktail/config.ini
i[default]
host = 127.0.0.1
username = username
password = MySecretPassword
scheme = https
port = 9243
```

The password will be stored in **plain text** so make sure it has 0400
permissions. I'll explore a way of encrypting this password.

## Usage

```
$ elktail -h
Usage: elktail [options]

Options:
  -h, --help            show this help message and exit
  -p PROCESS_NAME, --process=PROCESS_NAME
                        [optional] filter by process name
  -s SEVERITY, --severity=SEVERITY
                        [optional] filter by log severity (e.g.,
                        Informational, Warning, Error)
  -H HOSTNAME, --hostname=HOSTNAME
                        [optional] filter by hostname
  -q QUERY_STRING, --query=QUERY_STRING
                        [optional] string to search for in log messages
  -f, --follow          [optional] follow log output (like tail -f)
  -n LIMIT, --lines=LIMIT
                        [optional] number of initial lines to show (default:
                        10)
  -v, --verbose         increase output verbosity (-v or -vv)
```

* Arguments can be used at the same time or no arguments at all
* Arguments works as **and**

### No arguments

Executing elktail with no arguments, will **tailf** everything in the filebeat
indexes.

```
$ elktail
2020-06-30T21:27:32.227Z :: [2020-06-30 21:27:32,227: INFO/MainProcess] Received task: tasks.s3_campaigns.monitor_incoming_files.monitor[acc61ad7-5890-41d6-8fa0-93e5547df61a]
2020-06-30T21:27:47.289Z :: [2020-06-30 21:27:47,289: INFO/ForkPoolWorker-66] Task tasks.reports.check_scheduled_reports.check_something[668d7f0e-7a86-4cb1-9e55-6197a8a1a6a3] succeeded in 0.006264386989641935s: True
2020-06-30T21:27:05.222Z :: [2020-06-30 21:27:05,222: INFO/ForkPoolWorker-287] Task tasks.reports.check_scheduled_reports.check_something[2c55f42e-2bbf-4448-9445-5f16a90338bd] succeeded in 0.003620134957600385s: True
```

# ELKTAIL

ELKTail is a command-line utility, similar to `tail -f`, designed for streaming and searching logs stored in Elasticsearch. It's particularly useful for developers and system administrators who need to monitor real-time log data or quickly search through recent log history.

## Features

*   **Real-time Log Tailing**: Follow logs as they are indexed into Elasticsearch, similar to `tail -f`.
*   **Historical Log Search**: Fetch and display a specified number of recent log entries.
*   **Filtering**:
    *   Filter logs by process name (`-p` or `--process`).
    *   Filter logs by severity level (`-s` or `--severity`) (e.g., Informational, Warning, Error).
    *   Filter logs by hostname (`-H` or `--hostname`).
    *   **NEW**: Filter logs by a query string within the message content (`-q` or `--query`).
*   **Configurable Output**:
    *   Control the number of initial lines displayed (`-n` or `--lines`).
    *   Adjust verbosity to show more or less detail (`-v`, `-vv`).
    *   **IMPROVED**: Severity text (e.g., `[Error]`, `[Warning]`) is now always displayed for clarity.
*   **Timezone Conversion**: Timestamps are converted to `Europe/Amsterdam` for readability.
*   **Duplicate Prevention**: Avoids displaying duplicate log entries within a fetched batch.
*   **IMPROVED**: More efficient fetching of the last N lines when not in follow mode, ensuring the *actual* most recent N lines are shown chronologically.

## Installation


