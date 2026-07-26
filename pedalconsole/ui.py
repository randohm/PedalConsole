import os
import subprocess
import logging
from . import constants, application, alsa
import alsaaudio
from collections.abc import Callable
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio

log = logging.getLogger(__name__)


class MixerWindow(Gtk.Window):
    def __init__(self, config:dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = kwargs['parent']
        self.config = config
        self.mixerdevices = []
        self.set_name("mixer-window")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_modal(True)
        self.set_default_size(config['window']['width'], config['window']['height'])

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.set_hexpand(True)
        self.main_box.set_vexpand(True)
        self.set_child(self.main_box)
        self.close_button = Gtk.Button.new_with_label("Close")
        self.close_button.set_hexpand(True)
        self.main_box.append(self.close_button)
        self.close_button.connect('clicked', self.on_close_click)

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.set_vexpand(True)
        self.scrolled_window.set_kinetic_scrolling(True)
        self.scrolled_window.set_policy(Gtk.PolicyType.ALWAYS, Gtk.PolicyType.NEVER)
        self.main_box.append(self.scrolled_window)

        self.mixer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.scrolled_window.set_child(self.mixer_box)
        self.audiodevice = alsa.AudioDevice(device_name=config['alsa']['device'])
        for m in self.audiodevice.mixers:
            #log.debug("adding mixer '%s'" % m)
            mixerdevice = self.audiodevice.get_mixer(m)
            self.mixerdevices.append(mixerdevice)
            mixercontrol = MixerControl(audiodevice=self.audiodevice, mixername=m, channels=None)
            self.mixer_box.append(mixercontrol)
            #break

        self.key_event_controller = Gtk.EventControllerKey.new()
        self.key_event_controller.connect('key-pressed', self.on_keypress)
        self.add_controller(self.key_event_controller)

    def on_keypress(self, controller:Gtk.EventControllerKey, keyval:int, keycode:int, state:Gdk.ModifierType):
        #log.debug("keypressed: %s %s %s" % (keyval, keycode, state))
        ctrl_pressed = state & Gdk.ModifierType.CONTROL_MASK
        cmd_pressed = state & Gdk.ModifierType.META_MASK
        if keyval in (ord('w'), ord('W')) and (ctrl_pressed or cmd_pressed):
            log.debug("MixerWindow closing")
            self.close()

    def on_close_click(self, button:Gtk.Button):
        log.debug("MixerWindow closing")
        self.close()

class MuteButton(Gtk.Button):
    def __init__(self, audiodevice:alsa.AudioDevice, mixerdevice:alsaaudio.Mixer, on_click:Callable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if mixerdevice.getmute()[0]:
            self.mute = True
            self.add_css_class("muted")
        else:
            self.mute = False
            self.add_css_class("unmuted")
        self.audiodevice = audiodevice
        self.mixerdevice = mixerdevice
        self.set_name("mute-button")
        if self.mute:
            self.set_label(constants.UNMUTE_BUTTON_LABEL)
        else:
            self.set_label(constants.MUTE_BUTTON_LABEL)
        self.connect('clicked', on_click)

    def toggle_mute(self):
        if self.mute:
            log.debug("Unmuting mixer '%s'" % self.mixerdevice.mixer())
            self.mixerdevice.setmute(False)
            self.set_label(constants.MUTE_BUTTON_LABEL)
            self.mute = False
            self.remove_css_class("muted")
            self.add_css_class("unmuted")
        else:
            log.debug("Muting mixer '%s'" % self.mixerdevice.mixer())
            self.mixerdevice.setmute(True)
            self.set_label(constants.UNMUTE_BUTTON_LABEL)
            self.mute = True
            self.remove_css_class("unmuted")
            self.add_css_class("muted")

class RestartDialog(Gtk.AlertDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_modal(True)
        self.set_message(constants.DIALOG_MESSAGE_FMT % "Restart app and services?")
        self.set_detail(constants.DIALOG_DETAIL_FMT % "FULL = all services and UI restarted\nSERVICE = services only\nAPP = UI/App only")
        self.set_buttons(["NO", "FULL", "SERVICE", "APP"])

class PowerDialog(Gtk.AlertDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_modal(True)
        self.set_message(constants.DIALOG_MESSAGE_FMT % "Reboot or Power off?")
        self.set_detail(constants.DIALOG_DETAIL_FMT % "Restart or turn off device")
        self.set_buttons(["NO", "REBOOT", "POWER OFF"])

class StatLabel(Gtk.Label):
    def __init__(self, stat:str, value:str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_name("stat-label")
        self.set_justify(Gtk.Justification.CENTER)
        self.stat = stat
        self.set_value(value)

    def set_value(self, value):
        self.set_markup(constants.STATLABEL_FMT % (value, self.stat))

class MixerSlider(Gtk.Scale):
    def __init__(self, audiodevice:alsa.AudioDevice, mixerdevice:alsaaudio.Mixer, channel:int|None, on_value_changed:Callable, *args, **kwargs):
        adjustment = Gtk.Adjustment(value=0, step_increment=1, lower=0, upper=100)
        super().__init__(orientation=Gtk.Orientation.VERTICAL, adjustment=adjustment, *args, **kwargs)
        self.audiodevice = audiodevice
        self.mixerdevice = mixerdevice
        self.channel = channel
        self.set_name("mixer-slider")
        self.set_vexpand(True)
        self.set_inverted(True)
        self.add_mark(0, Gtk.PositionType.LEFT, "")
        self.add_mark(0, Gtk.PositionType.RIGHT, "")
        self.add_mark(100, Gtk.PositionType.LEFT, "")
        self.add_mark(100, Gtk.PositionType.RIGHT, "")
        self.set_value(self.audiodevice.get_volume_percent(self.mixerdevice)[channel if channel is not None else 0])
        self.connect('value-changed', on_value_changed)

class MixerControl(Gtk.Box):
    def __init__(self, audiodevice:alsa.AudioDevice, mixername:str, channels:int|None, displayname:str|None=None, *args, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, *args, **kwargs)
        log.debug("Creating mixercontrol for '%s' '%s'" % (audiodevice.device_name, mixername))
        self.audiodevice = audiodevice
        self.mixername = mixername
        self.channels = channels
        self.displayname = displayname if displayname is not None else mixername
        self.mixerdevice = audiodevice.get_mixer(mixername)
        self.set_name("mixer-control")
        self.set_vexpand(True)
        self.set_halign(Gtk.Align.CENTER)
        self.name_label = Gtk.Label()
        self.name_label.set_name("mixer-name-label")
        self.name_label.set_markup("<b>%s</b>" % self.displayname)
        self.name_label.set_justify(Gtk.Justification.CENTER)
        self.name_label.set_wrap(True)
        self.append(self.name_label)

        volume_cap = self.mixerdevice.volumecap()
        enum_controls = self.mixerdevice.getenum()
        if len(volume_cap) > 0:
            ## Add volume slider if capabilities exist
            self.sliders_grid = Gtk.Grid()
            self.sliders_grid.set_name("mixer-sliders-grid")
            self.sliders_grid.set_halign(Gtk.Align.CENTER)
            self.append(self.sliders_grid)
            self.sliders = []
            self.level_labels = []
            if channels is None:
                self.setup_slider(channel=channels)
            else:
                for c in range(channels):
                    self.setup_slider(channel=c)
        elif len(enum_controls) > 0:
            ## Add enumerated control if capability exists
            log.debug("Enum for mixer '%s': %s" % (self.mixername, enum_controls))
            self.enum_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.enum_box.set_vexpand(True)
            self.append(self.enum_box)
            selected_item = None
            for i in range(len(enum_controls[1])):
                if enum_controls[0] == enum_controls[1][i]:
                    selected_item = i
                    break
            self.enum_dropdown = Gtk.DropDown.new_from_strings(enum_controls[1])
            self.enum_dropdown.set_name("mixer-enum-dropdown")
            self.enum_dropdown.set_selected(selected_item)
            self.enum_box.append(self.enum_dropdown)
            self.enum_dropdown.connect("notify::selected", self.on_enum_selected)
        else:
            spacer_box = Gtk.Box()
            spacer_box.set_vexpand(True)
            self.append(spacer_box)

        if len(self.mixerdevice.switchcap()) > 0:
            ## Add mute button if capability exists
            self.mute_button = MuteButton(audiodevice=self.audiodevice, mixerdevice=self.mixerdevice, on_click=self.on_mute_button_clicked)
            self.append(self.mute_button)

    def setup_slider(self, channel:int|None):
        if channel is None:
            column = 0
        else:
            column = channel
        label = Gtk.Label()
        label.set_markup(constants.VOLUME_LABEL_FMT % self.audiodevice.get_volume_db(mixer=self.mixerdevice)[column])
        label.set_name("volume-label")
        self.level_labels.append(label)
        self.sliders_grid.attach(label, column, 0, 1, 1)
        slider = MixerSlider(audiodevice=self.audiodevice, mixerdevice=self.mixerdevice, channel=channel, on_value_changed=self.on_slider_changed)
        slider.set_name("mixer-slider")
        self.sliders.append(slider)
        self.sliders_grid.attach(slider, column, 1, 1, 1)

    def on_mute_button_clicked(self, button:Gtk.Button):
        log.debug("Mute button clicked for mixer '%s'" % self.mixername)
        button.toggle_mute()

    def on_slider_changed(self, scale:Gtk.Scale):
        value = scale.get_value()
        log.debug("slider value_changed for '%s' channel '%s': %f" % (scale.mixerdevice.mixer(), scale.channel, value))
        self.audiodevice.set_volume_percent(mixer=self.mixerdevice, volume=int(value), channel=scale.channel)
        vol_db = self.audiodevice.get_volume_db(mixer=self.mixerdevice)[scale.channel if scale.channel is not None else 0]
        log.debug("vol_db: %s" % vol_db)
        vol_markup = constants.VOLUME_LABEL_FMT % vol_db
        if vol_db == -99999.99:
            vol_markup = "off"
        self.level_labels[scale.channel if scale.channel is not None else 0].set_markup(vol_markup)

    def on_enum_selected(self, dropdown, pspec):
        selected = dropdown.get_selected()
        log.debug("enum selected: %d" % selected)
        self.mixerdevice.setenum(selected)

class MixerSideBox(Gtk.Box):
    def __init__(self, config:dict, label_markup:str, audiodevice:alsa.AudioDevice, *args, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, *args, **kwargs)
        log.debug("Mixer side box config: %s" % config)
        self.config = config
        self.audiodevice = audiodevice
        self.set_name("side-box")
        #self.set_hexpand(True)
        self.set_vexpand(True)

        self.top_label = Gtk.Label()
        self.top_label.set_markup(label_markup)
        self.top_label.set_name("side-label")
        self.append(self.top_label)

        self.mixer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.mixer_box.set_name("mixer-box")
        self.mixer_box.set_vexpand(True)
        self.append(self.mixer_box)

        for m in config:
            log.debug("MixerControl config: %s" % m)
            channels = None
            if 'channels' in m:
                channels = m['channels']
            displayname = None
            if 'displayname' in m:
                displayname = m['displayname']
            mc = MixerControl(audiodevice=self.audiodevice, mixername=m['mixername'], channels=channels, displayname=displayname)
            self.mixer_box.append(mc)

class CommandButton(Gtk.Button):
    def __init__(self, config:dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_name("command-button")
        self.config = config
        self.set_label(config['label'])
        self.popen_process = None
        if 'warning' in config and config['warning']:
            self.connect("clicked", self.show_warning)
        else:
            self.connect("clicked", self.exec_commands)

    def exec_commands(self, button:Gtk.Button):
        log.debug("Commands: %s" % self.config['commands'])
        if self.config['fork']:
            if hasattr(self, "popen_process") and self.popen_process and self.popen_process.poll() is None:
                log.debug("Command already running")
            else:
                if constants.EXEC_CMDS:
                    for cmd in self.config['commands']:
                        self.popen_process = subprocess.Popen(cmd, shell=True)
        else:
            for cmd in self.config['commands']:
                if constants.EXEC_CMDS:
                    subprocess.run(cmd, shell=True)

    def show_warning(self, button:Gtk.Button):
        if 'warning' not in self.config:
            raise ValueError("Missing 'warning' in config")
        dialog = Gtk.AlertDialog()
        dialog.set_modal(True)
        dialog.set_message(constants.DIALOG_MESSAGE_FMT % self.config['warning'])
        #dialog.set_detail("")
        dialog.set_buttons(["NO", "YES"])
        dialog.choose(parent=self.get_ancestor(Gtk.Window), callback=self.warning_response)

    def warning_response(self, dialog:Gtk.AlertDialog, async_result:Gio.AsyncResult):
        try:
            res = dialog.choose_finish(async_result)
            log.debug("dialog response %s" % res)
            if res:
                self.exec_commands(None)
        except Exception as e:
            log.error("Dialog error: %s" % e)

class CustomButtonsGrid(Gtk.Grid):
    def __init__(self, config:dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)
        log.debug("buttons: %s" % self.config)
        self.buttons = []
        for button_config in self.config:
            b = CommandButton(config=button_config)
            self.buttons.append(b)
            self.attach(b, button_config['geometry']['column'], button_config['geometry']['row'],
                                    button_config['geometry']['width'], button_config['geometry']['height'])

class StatsGrid(Gtk.Grid):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)
        self.set_name("stats-grid")
        self.cpu_label = StatLabel("CPU", "")
        self.mem_label = StatLabel("Mem", "")
        self.temp_label = StatLabel("Temp", "")
        self.samplerate_label = StatLabel("Rate", "")
        self.bits_label = StatLabel("Bits", "")
        self.buffer_label = StatLabel("Buffer", "")
        self.attach(self.cpu_label, 0, 0, 1, 1)
        self.attach(self.mem_label, 1, 0, 1, 1)
        self.attach(self.temp_label, 2, 0, 1, 1)
        self.attach(self.samplerate_label, 0, 1, 1, 1)
        self.attach(self.bits_label, 1, 1, 1, 1)
        self.attach(self.buffer_label, 2, 1, 1, 1)

class StockButtonsGrid(Gtk.Grid):
    def __init__(self, config:dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.mixer_running = False
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)
        self.set_name("stock-button-box")
        self.mixer_button = Gtk.Button(label=constants.BUTTON_LABEL_MIXER)
        self.mixer_button.set_name("stock-button")
        self.mixer_button.set_hexpand(True)
        self.mixer_button.connect("clicked", self.mixer_button_clicked)
        self.restart_button = Gtk.Button(label=constants.BUTTON_LABEL_RESTART)
        self.restart_button.set_name("stock-button")
        self.restart_button.set_hexpand(True)
        self.restart_button.connect("clicked", self.restart_button_clicked)
        self.power_button = Gtk.Button(label=constants.BUTTON_LABEL_POWER)
        self.power_button.set_name("stock-button")
        self.power_button.set_hexpand(True)
        self.power_button.connect("clicked", self.power_button_clicked)

        self.attach(self.mixer_button, 0, 0, 2, 1)
        self.attach(self.restart_button, 0, 1, 1, 1)
        self.attach(self.power_button, 1, 1, 1, 1)

    def power_button_clicked(self, button:Gtk.Button):
        PowerDialog().choose(callback=self.power_dialog_response)

    def power_dialog_response(self, dialog:Gtk.AlertDialog, async_result):
        try:
            res = dialog.choose_finish(async_result)
            log.debug("Power response %s" % res)
            if res == 1:
                log.debug("Running '%s'" % self.config['commands']['reboot'])
                for cmd in self.config['commands']['reboot']:
                    if constants.EXEC_CMDS:
                        subprocess.run(cmd, shell=True)
            elif res == 2:
                log.debug("Running '%s'" % self.config['commands']['poweroff'])
                for cmd in self.config['commands']['poweroff']:
                    if constants.EXEC_CMDS:
                        subprocess.run(cmd, shell=True)
        except Exception as e:
            log.debug("Power operation failed %s" % e)

    def restart_button_clicked(self, button:Gtk.Button):
        RestartDialog().choose(callback=self.restart_dialog_response)

    def restart_dialog_response(self, dialog:Gtk.AlertDialog, async_result):
        try:
            res = dialog.choose_finish(async_result)
            log.debug("Restart response %s" % res)
            if res == 1:
                log.debug("Full restart")
                for cmd in [*self.config['commands']['restart_service'], *self.config['commands']['restart_console']]:
                    log.debug("Running '%s'" % cmd)
                    if constants.EXEC_CMDS:
                        subprocess.run(cmd, shell=True)
            elif res == 2:
                log.debug("Half restart")
                for cmd in self.config['commands']['restart_service']:
                    log.debug("Running '%s'" % cmd)
                    if constants.EXEC_CMDS:
                        subprocess.run(cmd, shell=True)
            elif res == 3:
                log.debug("Restarting UI")
                for cmd in self.config['commands']['restart_console']:
                    log.debug("Running '%s'" % cmd)
                    if constants.EXEC_CMDS:
                        subprocess.run(cmd, shell=True)
        except Exception as e:
            log.debug("Restart failed %s" % e)

    def mixer_button_clicked(self, button:Gtk.Button):
        log.debug("Mixer button clicked")
        MixerWindow(config=self.config, parent=self.get_ancestor(Gtk.Window)).present()

class PedalConsoleWindow(Gtk.ApplicationWindow):
    def __init__(self, config:dict, css_file:str, audiodevice:alsa.AudioDevice, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = application
        self.config = config
        self.css_file = css_file
        self.audiodevice = audiodevice

        if css_file and os.path.isfile(css_file):
            log.debug("reading css file: %s" % css_file)
            self.css_provider = Gtk.CssProvider.new()
            try:
                self.css_provider.load_from_path(css_file)
            except Exception as e:
                log.error("could not load CSS: %s" % e)
                self.css_provider = None
            display = Gtk.Widget.get_display(self)
            Gtk.StyleContext.add_provider_for_display(display, self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.set_title(constants.WIND0W_TITLE)
        self.set_default_size(config['window']['width'], config['window']['height'])
        self.set_decorated(config['window']['decorated'])
        self.set_resizable(config['window']['resizable'])
        if config['window']['fullscreen']:
            self.fullscreen()

        self.key_event_controller = Gtk.EventControllerKey.new()
        self.key_event_controller.connect('key-pressed', self.on_keypress)
        self.add_controller(self.key_event_controller)

        ## Setup main container
        self.main_box = Gtk.Box()
        self.main_box.set_name("main-box")
        self.set_child(self.main_box)

        self.output_box = MixerSideBox(config=self.config['alsa']['output'], audiodevice=self.audiodevice, label_markup=constants.LABEL_OUTPUT)
        self.input_box = MixerSideBox(config=self.config['alsa']['input'], audiodevice=self.audiodevice, label_markup=constants.LABEL_INPUT)

        self.main_box.append(self.output_box)
        self.center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.center_box.set_name("center-box")
        self.main_box.append(self.center_box)

        self.custom_buttons_grid = CustomButtonsGrid(self.config['buttons'])
        self.center_box.append(self.custom_buttons_grid)

        ## Middle spacer
        spacer_box = Gtk.Box()
        spacer_box.set_vexpand(True)
        self.center_box.append(spacer_box)

        self.stats_grid = StatsGrid()
        self.stock_buttons_grid = StockButtonsGrid(config=self.config)
        self.center_box.append(self.stats_grid)
        self.center_box.append(self.stock_buttons_grid)
        self.main_box.append(self.input_box)

    def on_keypress(self, controller:Gtk.EventControllerKey, keyval:int, keycode:int, state:Gdk.ModifierType):
        #log.debug("keypressed: %s %s %s" % (keyval, keycode, state))
        ctrl_pressed = state & Gdk.ModifierType.CONTROL_MASK
        cmd_pressed = state & Gdk.ModifierType.META_MASK
        if keyval in (ord('q'), ord('Q')) and (ctrl_pressed or cmd_pressed):
            log.debug("QUIT pressed")
            self.close()
