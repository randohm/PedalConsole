import re
import sys, time, platform
import logging
import psutil
import threading
from . import ui, constants, alsa
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

log = logging.getLogger(__name__)

class StatsUpdater():
    def __init__(self, window, config):
        self.window = window
        self.config = config
        try:
            self.thread = threading.Thread(target=self.thread_run, daemon=True)
            self.thread.start()
        except Exception as e:
            log.error("Failed to start thread: %s" % e)
            raise e

    def thread_run(self):
        while not self.window.is_active():
            time.sleep(0.1)
        while True:
            cpu_usage = psutil.cpu_percent(interval=constants.STATS_UPDATE_INTERVAL)
            #log.debug("CPU usage: %s" % cpu_usage)
            GLib.idle_add(self.window.cpu_label.set_value, "%-03.1f%%" % cpu_usage)

            mem_usage = psutil.virtual_memory().percent
            #log.debug("MEM usage: %s" % mem_usage)
            GLib.idle_add(self.window.mem_label.set_value, "%-03.1f%%" % mem_usage)

            if psutil.LINUX:
                temps = psutil.sensors_temperatures()
                #log.debug("Temps: %s" % temps['cpu_thermal'][0].current)
                GLib.idle_add(self.window.temp_label.set_value, "%3.1fC" % temps['cpu_thermal'][0].current)

                try:
                    with open(constants.ALSA_PROC_FILE_FMT % self.config['alsa']['device'], "r") as f:
                        lines = f.read().splitlines()
                        #log.debug("ALSA proc file: %s" % lines)
                        if lines[0] == "closed\n":
                            GLib.idle_add(self.window.samplerate_label.set_value, "0")
                            GLib.idle_add(self.window.bits_label.set_value, "0")
                        else:
                            rate = None
                            bits = None
                            for l in lines:
                                #log.debug("proc file line: %s" % l)
                                if re.match(r"rate:", l):
                                    rate = re.search(r"^rate: ([0-9]+)", l).group(1)
                                elif re.match(r"format:", l):
                                    bits = re.search(r"format: [^0-9]*([0-9]+)[^0-9]*", l).group(1)
                            #log.debug("Rate: %s" % rate)
                            #log.debug("Bits: %s" % bits)
                            GLib.idle_add(self.window.samplerate_label.set_value, rate)
                            GLib.idle_add(self.window.bits_label.set_value, bits)
                except Exception as e:
                    log.error("Failed to open alsa proc file: %s" % e)
            time.sleep(constants.STATS_UPDATE_INTERVAL)



class PedalConsoleApp(Gtk.Application):
    def __init__(self, config, css_file, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.css_file = css_file
        self.audiodevice = alsa.AudioDevice(device_name=config['alsa']['device'])

        self.connect('activate', self.on_activate)
        self.connect('shutdown', self.on_quit)

    def on_quit(self, app):
        self.quit()

    def on_activate(self, app):
        self.window = ui.PedalConsoleWindow(application=self, config=self.config, css_file=self.css_file,
                                            audiodevice=self.audiodevice)
        try:
            self.statsupdater = StatsUpdater(window=self.window, config=self.config)
        except Exception as e:
            log.fatal("Failed to start statsupdater: %s" % e)
            sys.exit(1)
        self.window.present()
