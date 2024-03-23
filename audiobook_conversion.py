from elevenlabslib import *
from elevenlabslib.helpers import *
import keyring, requests, soundfile

audiobook_url = 'https://www.archive.org/download/1912_shortworks_0906_librivox/014-peacewarbalkans_angell.mp3' # This is a public domain audiobook.
print("Downloading audiobook...")
audiobook_bytes = requests.get(audiobook_url).content
audiobook_sf = soundfile.SoundFile(io.BytesIO(audiobook_bytes)) # Just used to get the duration of the audiobook.
# Play back the first 10 seconds of it.
audio_stream = play_audio_v2(audiobook_bytes, playbackOptions=PlaybackOptions(runInBackground=True))
time.sleep(10)
audio_stream.abort()
# Select the voice to use.
user = User(keyring.get_password("bytes_and_bobs", "elevenlabs_api_key"))
voice = user.get_voice_by_ID("TQ6BHf6fzLzIzjg6hjh6")  # Just pick a random voice, could be any.
start_time = time.perf_counter()
# Run the conversion by splitting it up in chunks <5min (using Silero-VAD to cut it when sentences end), running it in parallel and rejoining it.
print("Converting audiobook...")
converted_audiobook_bytes = sts_long_audio(audiobook_bytes, voice, generation_options=GenerationOptions(model_id="eleven_english_sts_v2"))  #English-only model since it's faster, otherwise defaults to multilingual.
print(f"Time taken for conversion: {int((time.perf_counter()-start_time)/60)} minutes, for a {int(audiobook_sf.frames/audiobook_sf.samplerate/60)} minute audiobook.")
# Play a sample of the converted audiobook.
audio_stream = play_audio_v2(converted_audiobook_bytes, playbackOptions=PlaybackOptions(runInBackground=True))
time.sleep(10)
audio_stream.abort()
# Save it.
output_audio_file_path = os.path.join(r"C:\Users\lugia19\Desktop 3\converted-audiobook.mp3")
save_audio_v2(converted_audiobook_bytes, output_audio_file_path, "mp3")