# An example of how to apply soundboard effects to an audio playback.

from pedalboard import *
from elevenlabslib import *
import keyring
xi_api_key = keyring.get_password("bytes_and_bobs", "elevenlabs_api_key")

user = ElevenLabsUser(xi_api_key)
voice = user.get_available_voices()[0]

ROBOT = Pedalboard(
        [
            PitchShift(semitones=-1),
            Delay(delay_seconds=0.01, feedback=0.5, mix=0.2),
            Chorus(rate_hz=0.5, depth=0.8, mix=0.5, centre_delay_ms=2, feedback=0.3),
            Reverb(
                room_size=0.05, dry_level=0.5, wet_level=0.5, freeze_mode=0.5, width=0.3
            ),
            Gain(gain_db=8),
        ]
    )

voice.generate_stream_audio_v2("This is a test audio, which should not have the robot filter applied.")
voice.generate_stream_audio_v2("This is a test audio, which should have the robot filter applied.", PlaybackOptions(audioPostProcessor=ROBOT.process))

