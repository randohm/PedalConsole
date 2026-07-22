import sys, os
import argparse
import logging
import signal
import yaml
from .application import PedalConsoleApp
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio

from . import constants, application, ui

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
formatter = logging.Formatter(constants.LOG_FORMAT)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
log.addHandler(handler)


def signal_exit(sig, frame):
    log.debug("caught signal %s, exiting" % signal.Signals(sig).name)
    sys.exit(0)


def main():
    log.debug("starting pedalconsole")
    for k in sorted(os.environ.keys()):
        log.debug("os.environ[%s]=%s", k, os.environ[k])
    signal.signal(signal.SIGINT, signal_exit)
    signal.signal(signal.SIGTERM, signal_exit)

    ## parse args
    arg_parser = argparse.ArgumentParser(description="Pedal Console", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    arg_parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose output")
    arg_parser.add_argument("-c", "--config", action='store', help="Config file", required=True)
    arg_parser.add_argument("-s", "--css", action='store', help="CSS file", required=True)
    parsed_args = arg_parser.parse_args()

    config = yaml.safe_load(open(parsed_args.config))
    log.debug("config: %s", config)

    if not 'console' in config:
        log.fatal("Missing 'console' section in config")
        return 1
    app = PedalConsoleApp(config['console'], parsed_args.css)
    app.run()
    log.debug("exiting pedalconsole")
    return 0