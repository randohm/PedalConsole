import logging
import websockets, websockets.sync.client, requests
import mido
import threading

log = logging.getLogger(__name__)
retry_wait = 2


class BridgeConnection:
    def __init__(self, url:str, *args, **kwargs):
        self.url = url
    def send(self, message) -> bool:
        pass

class HttpConnection(BridgeConnection):
    def __init__(self, url:str, *args, **kwargs):
        super().__init__(url, *args, **kwargs)

    def send(self, message) -> bool:
        full_url = self.url + message
        log.debug("http calling url: %s" % full_url)
        res = requests.get(full_url)
        if res.status_code == 200:
            return True
        else:
            log.error("http call failed: %s" % res.status_code)
            return False

class WebsocketConnection(BridgeConnection):
    def __init__(self, url:str, *args, **kwargs):
        super().__init__(url, *args, **kwargs)
        log.debug("websocket url: %s" % url)
        self.ws = websockets.sync.client.connect(url)

    def send(self, message) -> bool:
        log.debug("websocket sending message: %s" % message)
        try:
            self.ws.send(message)
        except Exception as e:
            log.error("failed to send to %s: %s" % (self.url, e))
            return False
        return True

class MidiBridge:
    def __init__(self, config:dict):
        self.config = config
        #log.debug("midibridge config: %s" % config)
        self.threads = []
        self.ports = []
        self.bridges = {}
        for c in config:
            log.debug("midibridge cfg: %s" % c)
            brconnection = None
            if c['remote_type'] == 'websocket':
                try:
                    brconnection = WebsocketConnection(c['url'])
                except Exception as e:
                    log.error("midibridge error opening websocket: %s" % e)
                    continue
            elif c['remote_type'] == 'http':
                brconnection = HttpConnection(c['url'])
            for p in c['presets']:
                log.debug("midibridge preset: %s" % p)
                if not p['channel'] in self.bridges:
                    self.bridges[p['channel']] = {}
                if 'cc' in p:
                    if not 'cc' in self.bridges[p['channel']]:
                        self.bridges[p['channel']]['cc'] = {}
                    if not 'cc_value' in p:
                        ## All CC's need a value
                        raise Exception("midibridge presets must have 'cc_value' key")
                    if not p['cc'] in self.bridges[p['channel']]['cc']:
                        self.bridges[p['channel']]['cc'][p['cc']] = {}
                    if not p['cc_value'] in self.bridges[p['channel']]['cc'][p['cc']]:
                        self.bridges[p['channel']]['cc'][p['cc']][p['cc_value']] = {}
                    self.bridges[p['channel']]['cc'][p['cc']][p['cc_value']] = {
                        "connection": brconnection,
                        "command": c['command_fmt'] % tuple(p['params'])
                    }
                elif 'pc' in p:
                    if not 'pc' in self.bridges[p['channel']]:
                        self.bridges[p['channel']]['pc'] = {}
                    if not p['pc'] in self.bridges[p['channel']]['pc']:
                        self.bridges[p['channel']]['pc'][p['pc']] = {
                            "connection": brconnection,
                            "command": c['command_fmt'] % tuple(p['params'])
                        }
        log.debug("bridges: %s" % self.bridges)
        port_names = mido.get_input_names()
        for p in port_names:
            log.debug("midibridge input: %s" % p)
            port = mido.open_input(name=p, callback=self.on_message_received)
            self.ports.append(port)

    def on_message_received(self, message):
        log.debug("midibridge message: %s" % message)
        channel = message.channel + 1
        if not channel in self.bridges:
            return
        if message.type == "control_change":
            if not message.control in self.bridges[channel]['cc']:
                return
            if not message.value in self.bridges[channel]['cc'][message.control]:
                return
            log.debug("CC is defined: %s" % self.bridges[channel]['cc'][message.control][message.value])
            self.bridges[channel]['cc'][message.control][message.value]['connection'].send(self.bridges[channel]['cc'][message.control][message.value]['command'])
        elif message.type == "program_change":
            if not message.program in self.bridges[channel]['pc']:
                return
            self.bridges[channel]['pc'][message.program]['connection'].send(self.bridges[channel]['pc'][message.program]['command'])
            log.debug("PC is defined %s" % self.bridges[channel]['pc'][message.program])