import audioop
import math
import queue
import time
from collections import deque
from concurrent.futures import Future

import keyring
import pyaudio
import logging


from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone,
)
from elevenlabslib import *
from openai import Stream
from openai.types.chat import ChatCompletionChunk
from sounddevice import OutputStream
import openai

dg_api_key = keyring.get_password("bytes_and_bobs", "deepgram_api_key")
xi_api_key = keyring.get_password("bytes_and_bobs", "elevenlabs_api_key")
openai_api_key = keyring.get_password("bytes_and_bobs", "openai_api_key")

client = openai.OpenAI(api_key=openai_api_key)
user = ElevenLabsUser(xi_api_key)
voice = user.get_voices_by_name_v2("Dom")[0]

config = DeepgramClientOptions(
            api_key=dg_api_key,
            options={"keepalive": "true"}
        )
deepgram_client = DeepgramClient(config=config)

input_streamer = ReusableInputStreamer(voice, generationOptions=GenerationOptions(model="eleven_turbo_v2"), websocketOptions=WebsocketOptions(chunk_length_schedule=[100]))

sample_text = "This is just an example text. This would be instead substituted by the output of an LLM. But obviously I don't want to make calls while testing, so this will do."

message_history = [
    {
        "role":"system",
        "content":"You are an assistant taking part in a voice conversation."
                  "You will be informed when the user interrupts you during a response, and at what point they interrupted you."
                  "If there is a mistake or typo in the user's message, it is due to the speech recognition."
    }
]

def write_api(text):
    message_history.append({"role": "user", "content": text})

    openai_stream:Stream[ChatCompletionChunk] = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=message_history,
        stream=True,
        max_tokens=1024
    )
    for chunk in openai_stream:
        if chunk.choices[0].delta.content is not None:
            #print(chunk.choices[0].delta.content, end="")
            yield chunk.choices[0].delta.content


current_start_time = 0
stream_future:Future[OutputStream] = None
transcript_future:Future[queue] = None
current_transcript = ""
def set_start():
    global current_start_time
    current_start_time = time.perf_counter()

#Don't need the precision of character-level timestamps, so we can just do word-level.
def character_to_word_timestamps(char_timestamps):
    word_timestamps = []
    current_word = ""
    word_start_time = 0
    last_char_end_time = 0

    for char_dict in char_timestamps:
        char = char_dict['character']
        start_time = char_dict['start_time_ms']
        duration = char_dict['duration_ms']
        end_time = start_time + duration

        # Check if we're starting a new word
        if not current_word:
            word_start_time = start_time

        # Add character to current word if it's not a space (assuming space indicates new word)
        if char != ' ':
            current_word += char
            last_char_end_time = end_time
        else:
            # Append the current word and its timestamps to the list
            if current_word:
                word_timestamps.append({
                    'word': current_word,
                    'start_time_ms': word_start_time,
                    'end_timestamp_ms': last_char_end_time,
                    'duration_ms': last_char_end_time - word_start_time
                })
                current_word = ""

        # Handle the last word if there's no trailing space in the input
        if char_dict is char_timestamps[-1] and current_word:
            word_timestamps.append({
                'word': current_word,
                'start_time_ms': word_start_time,
                'end_timestamp_ms': last_char_end_time,
                'duration_ms': last_char_end_time - word_start_time
            })

    return word_timestamps

def main():
    try:
        dg_connection = deepgram_client.listen.live.v("1")

        def on_message(self, result, **kwargs):
            global current_transcript, stream_future, transcript_future
            sentence:str = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return  #Outright ignore ones with no text

            if result.is_final:
                if not sentence.endswith(" "):
                    sentence += " "
                current_transcript += sentence
                print(f"Appending '{sentence}' to transcript...")

            if result.speech_final:
                print(f"Sending complete transcript: '{sentence}'.")
                current_transcript = current_transcript.rstrip()
                stream_future, transcript_future = input_streamer.queue_audio(write_api(current_transcript), PlaybackOptions(runInBackground=True, onPlaybackStart=set_start))
                current_transcript = ""

            print("")


        def on_speechstart(self, speech_started, **kwargs):
            global current_start_time
            print("Speech start.")
            if transcript_future is not None and current_start_time > 0:
                trans_queue:queue.Queue = transcript_future.result()
                all_word_data = list()
                while not trans_queue.empty():
                    transcript_data = trans_queue.get()
                    if transcript_data is None:
                        break
                    word_data = character_to_word_timestamps(transcript_data)
                    all_word_data.extend(word_data)


                #At this point, we have all the word timestamps recieved so far.
                #Transcripts are always recieved before the audio, so we for sure know where we were interrupted.
                stream_future.result().abort()  #Stop the audio playback.

                time_delta = int((time.perf_counter()-current_start_time)*1000)
                current_start_time = -1
                print(f"{time_delta}ms have passed since the start of playback and the interruption.")
                last_word_index = 0
                #NOTE: I tried to just offset it, but it seems like GPT-4 assumes the sentence was spoken even if it was only partially so.
                #So instead, we look for the previous complete sentence.
                for idx, word_info in enumerate(all_word_data):
                    if word_info['end_timestamp_ms'] < time_delta:
                        last_word_index = idx
                    else:
                        break

                response_spoken = ""

                for i in range(last_word_index+1):
                    response_spoken = f"{response_spoken} {all_word_data[i]['word']}"
                response_spoken = response_spoken.strip()

                if last_word_index < len(all_word_data) - 1:
                    response_spoken += " [Interrupted by User]"

                print(f"LLM got to say: '{response_spoken.rstrip()}'.")
                message_history.append({"role": "assistant", "content": response_spoken})




        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speechstart)

        options = LiveOptions(
            language="en",
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            smart_format=True,
            model="nova",
            vad_events=True,
            endpointing="500"
        )
        dg_connection.start(options, addons=dict(myattr="hello"), test="hello")

        # Open a microphone stream on the default input device
        microphone = Microphone(dg_connection.send)

        # start microphone
        microphone.start()

        input("Press Enter to stop recording...\n\n")
        microphone.finish()
        dg_connection.finish()
        print("Finished")

    except Exception as e:
        print(f"Could not open socket: {e}")
        return


if __name__ == "__main__":
    main()
