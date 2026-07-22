import alsaaudio
import logging

log = logging.getLogger(__name__)

class AudioDevice():
    def __init__(self, device_name, *args, **kwargs):
        cards = alsaaudio.cards()
        log.debug("Audio cards: %s" % cards)
        self.card_index = None
        for i in range(len(cards)):
            if device_name == cards[i]:
                self.card_index = i
                break
        if self.card_index is None:
            raise Exception("Audio card not found")
        log.debug("card index: %d" % self.card_index)
        self.mixers = alsaaudio.mixers(self.card_index)
        #log.debug("Mixers: %s" % self.mixers)

    def get_mixer(self, mixername):
        for i in range(len(self.mixers)):
            if self.mixers[i] == mixername:
                return alsaaudio.Mixer(control=self.mixers[i], cardindex=self.card_index)
        return None

    def get_volume_db(self, mixer):
        vols = mixer.getvolume(pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_DB)
        log.debug("volume: %s" % vols)
        ret = []
        for v in vols:
            ret.append(float(v)/100)
        return ret

    def get_volume_percent(self, mixer):
        vols = mixer.getvolume(pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_PERCENTAGE)
        log.debug("volume: %s" % vols)
        ret = []
        for v in vols:
            ret.append(v)
        return ret

    def set_volume_percent(self, mixer, volume, channel):
        if channel is None:
            mixer.setvolume(volume=volume, pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_PERCENTAGE, channel=alsaaudio.MIXER_CHANNEL_ALL)
        else:
            mixer.setvolume(volume=volume, pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_PERCENTAGE, channel=channel)

    def get_range_db(self, mixer):
        vol_range = mixer.getrange(pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_DB)
        ret = []
        for r in vol_range:
            ret.append(float(r)/100)
        return ret

    def set_mute(self, mixer):
        mixer.setmute(mute=True)