#!/usr/bin/env python3

"""
This is a simple "payload" process to demonstrate system end-to-end workflow

It consumes entries, counts them in timed intervals
and outputs sum of consumed values in interval window
"""
import io
import json
import logging
import os
import sys

# setup logging to file
_log_fmt = "[%(asctime)s]:" + logging.BASIC_FORMAT
logging.basicConfig(stream=sys.stderr, format=_log_fmt, level=logging.DEBUG)

log = logging.getLogger()

log.info('start sample process')

INTERVAL = int(os.environ.get('WINDOW_SIZE', 5))


def process_window(window: list):
    log.info('process window and reset')
    w_size = len(window)
    last_seq = window[-1]['seq']
    w_seq_sum = sum([record['seq'] for record in window])
    return 'Size:%s,Sum:%s,lSeq:%s\n' % (w_size, w_seq_sum, last_seq)


def mainloop():
    sys.stdin: io.StringIO
    sys.stdout: io.StringIO
    window = []
    while True:
        try:
            value = sys.stdin.readline()
            log.debug('read value from stdin: %s', value.strip())
            window.append(json.loads(value))
            if len(window) == INTERVAL:
                result = process_window(window)
                window = []
                sys.stdout.write(result)
                log.debug('wrote value to stdout')
        except (InterruptedError, KeyboardInterrupt):
            log.exception('interruption received')
            exit(0)
        except:
            log.exception('unexpected exception')


if __name__ == '__main__':
    mainloop()
