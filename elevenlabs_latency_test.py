import dataclasses
import json
import time

import keyring
import numpy as np

import elevenlabslib.helpers
from elevenlabslib import *

user = ElevenLabsUser(keyring.get_password("bytes_and_bobs", "elevenlabs_api_key"))

from pedalboard import *
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

voice = user.get_available_voices()[0]      #Just uses whatever voice you have available
#logging.basicConfig(level=logging.DEBUG)

#Pick which mode to test (ONLY ONE SHOULD BE TRUE):
test_normal = True
test_websockets = False
test_sts = False

#NOTE: This only works with one set of values, due to how the reusable websocket works.
test_reusable_websocket = False

#Shared options:
#Models to test (for anything besides sts):
models_to_test = ["eleven_multilingual_v2"]

#Formats to test:
#If you have pcm _and_ mp3 formats, try to put them in the same order.
#For example, if the first mp3 format is the highest, the first PCM should also be the highest quality one.
#This makes it so the latencies will be compared between like for like.
formats_to_test = ["mp3_44100_192"]

#Latency optimization levels to test:
lat_opt_levels = [3]

#Number of test runs:
test_runs = 10

#Generation options to use:
gen_options = GenerationOptions(stability=0.7, similarity_boost=0.7, style=0, use_speaker_boost=False)

#Whether or not to apply the ROBOT effect using pedalboard:
use_effect = False


#Normal testing parameters:
#String to generate:
prompt = "This is a test string."

#Websocket testing parameters:
#String to generate:
websocket_string = f"My name is Max, nice to meet you!"


#STS testing parameters:
#Model to use:
sts_model = "eleven_english_sts_v2"
#Audio to use:
try:
    sts_source_audio = open(r"C:\Users\lugia19\Desktop 3\me.mp3", "rb")
except FileNotFoundError:
    sts_source_audio = None

playOptions = PlaybackOptions(runInBackground=False)
if use_effect:
    playOptions.audioPostProcessor = ROBOT.process

counter = 0
for val in [test_sts, test_normal, test_websockets, test_reusable_websocket]:
    if val:
        counter += 1
if counter >= 2 or counter == 0:
    raise ValueError("Please only test one mode at a time.")

websocketOptions = WebsocketOptions(buffer_char_length=0, try_trigger_generation=True, chunk_length_schedule=[50]) #No buffering, and minimize chunk size
if test_sts:
    models_to_test = [sts_model]
    prompt = sts_source_audio

def write():
    for _ in range(1):
        yield {"text":websocket_string, "flush":False}   #Ensure it flushes

mp3_results = {}
pcm_results = {}
ulaw_results = {}

if test_reusable_websocket:
    #if len(models_to_test) > 1 or len(formats_to_test) > 1 or len(lat_opt_levels) > 1:
    #    raise ValueError("test_reusable_websocket only works with one set of values!")

    reusable_input_streamer = elevenlabslib.helpers.ReusableInputStreamer(voice, websocketOptions=WebsocketOptions(try_trigger_generation=True, buffer_char_length=0),
                              generationOptions=GenerationOptions(model=models_to_test[0], output_format=formats_to_test[0], latencyOptimizationLevel=lat_opt_levels[0],
                                stability=gen_options.stability, similarity_boost=gen_options.similarity_boost,
                                style=gen_options.style, use_speaker_boost=gen_options.use_speaker_boost))
else:
    reusable_input_streamer = None

def test_latency():
    for j in range(test_runs):
        print(f"Test run {j}")
        for model_inner in models_to_test:
            if model_inner not in mp3_results:
                mp3_results[model_inner] = dict()
            if model_inner not in pcm_results:
                pcm_results[model_inner] = dict()
            if model_inner not in ulaw_results:
                ulaw_results[model_inner] = dict()

            for audioformat in formats_to_test:
                resultsDict = dict()
                if "pcm" in audioformat:
                    resultsDict = pcm_results[model_inner]
                elif "mp3" in audioformat:
                    resultsDict = mp3_results[model_inner]
                elif "ulaw" in audioformat:
                    resultsDict = ulaw_results[model_inner]
                og_audio_format = audioformat
                for level in lat_opt_levels:
                    audioformat = f"{og_audio_format} (LatencyOptLevel: {level})"
                    print(f"Testing audio format: {audioformat} on model {model_inner}")

                    if audioformat not in resultsDict:
                        resultsDict[audioformat] = list()

                    resultsList:list = resultsDict[audioformat]
                    generatorInstance = write()


                    inner_gen_options = dataclasses.replace(gen_options, model_id=model_inner, model=model_inner, output_format=og_audio_format, latencyOptimizationLevel=level)

                    if test_reusable_websocket:
                        #Need to change the input streamer settings...
                        reusable_input_streamer.change_settings(generationOptions=inner_gen_options, websocketOptions=websocketOptions)
                        time.sleep(2)   #Simulate waiting for the websocket to be ready (this is necessary so that it doesn't count against the latency)
                        start_time = time.perf_counter()  # Start timing with perf_counter
                        inner_play_options = dataclasses.replace(playOptions, onPlaybackStart=lambda: resultsList.append((time.perf_counter() - start_time) * 1000))

                        reusable_input_streamer.queue_audio(generatorInstance, inner_play_options)
                    else:
                        start_time = time.perf_counter()  # Start timing with perf_counter
                        inner_play_options = dataclasses.replace(playOptions, onPlaybackStart=lambda: resultsList.append((time.perf_counter() - start_time) * 1000))

                        voice.generate_stream_audio_v2(
                            generatorInstance if test_websockets else prompt,
                            playbackOptions=inner_play_options,
                            generationOptions=inner_gen_options,
                            websocketOptions=websocketOptions
                        )
test_latency()

def calculate_stats(values):
    values = np.array(values)
    stats = {
        'mean': np.mean(values),
        'standard deviation': np.std(values)
    }
    return stats


def print_stats(key, stats):
    print(f"{key} Stats:")
    for stat_key, value in stats.items():
        print(f"{stat_key}: {value:.2f}ms")


# Pair up the values from mp3_dict and pcm_dict based on the order of the keys
for model in models_to_test:
    print(f"\n\n----Results for {model}----")
    if len(ulaw_results[model].keys()) > 0:
        for ulaw_key, ulaw_values in ulaw_results[model].items():
            ulaw_stats = calculate_stats(ulaw_values)
            print()
            print_stats(ulaw_key, ulaw_stats)

    if len(mp3_results[model].keys()) == 0:
        for pcm_key, pcm_values in pcm_results[model].items():
            pcm_stats = calculate_stats(pcm_values)
            print()
            print_stats(pcm_key, pcm_stats)
    elif len(pcm_results[model].keys()) == 0:
        for mp3_key, mp3_values in mp3_results[model].items():
            mp3_stats = calculate_stats(mp3_values)
            print()
            print_stats(mp3_key, mp3_stats)
    else:
        for (mp3_key, mp3_values), (pcm_key, pcm_values) in zip(mp3_results[model].items(), pcm_results[model].items()):
            mp3_stats = calculate_stats(mp3_values)
            pcm_stats = calculate_stats(pcm_values)

            # Compute the mean difference
            differences = np.array(mp3_values) - np.array(pcm_values)
            mean_difference = np.mean(differences)
            std_difference = np.std(differences)

            # Print the statistics and mean difference
            print()
            print_stats(mp3_key, mp3_stats)
            print()
            print_stats(pcm_key, pcm_stats)
            print(f"\nMean Difference between {mp3_key} and {pcm_key}: {mean_difference:.2f}ms")
            print(f"\nStandard Deviation of Difference between {mp3_key} and {pcm_key}: {std_difference:.2f}ms\n")

all_raw = {
    "mp3": mp3_results,
    "pcm": pcm_results,
    "ulaw": ulaw_results
}
with open("results.json", 'w') as file:
    json.dump(all_raw, file, indent=4)

input("Test over - raw results written to results.json")