#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django.") from exc

    # Default to port 8018 for local VPS/dev runs when no runserver port is provided.
    # Usage: `python manage.py runserver` will use 127.0.0.1:8018 unless an explicit port is given.
    if len(sys.argv) == 1:
        # no args: behave as before (show help) — do not inject runserver
        pass
    else:
        # if runserver is invoked without a host:port, append default host:port
        if sys.argv[1] == 'runserver' and len(sys.argv) == 2:
            sys.argv.append('127.0.0.1:8018')

    execute_from_command_line(sys.argv)
