# ELKTAIL

ELKTAIL is a command-line tool that generates a tail-like stream from Filebeat indices in Elasticsearch, allowing you to monitor and search logs in real-time.

## Features

* **Real-time Log Tailing**: Follow logs as they are indexed into Elasticsearch (similar to `tail -f`)
* **Historical Log Search**: Access and display recent log entries with configurable time ranges
* **Flexible Filtering**:
  * Process name filtering (`-p` or `--process`)
  * Severity level filtering (`-s` or `--severity`)
  * Hostname filtering (`-H` or `--hostname`)
  * Message content filtering (`-q` or `--query`)
* **Configurable Output**:
  * Adjustable initial line count (`-n` or `--lines`)
  * Verbosity control (`-v`, `-vv`)
  * Clear severity level indicators (`[Error]`, `[Warning]`, etc.)
* **Smart Configuration**: Automatically creates and manages configuration in the current directory



