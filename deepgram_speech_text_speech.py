#An example of using input streaming on elevenlabs with the partial transcripts from deepgram.
#Might have some issues, haven't finished polishing it up yet.

import queue
import threading
import keyring

from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone,
)
from elevenlabslib import *
dg_api_key = keyring.get_password("bytes_and_bobs", "deepgram_api_key")
xi_api_key = keyring.get_password("bytes_and_bobs", "elevenlabs_api_key")

class SharedGenerator:
    def __init__(self):
        self.queue = queue.Queue()
        self.end_event = threading.Event()
        self.token_count = 0

    def add_item(self, item):
        """Add an item to the queue."""
        if not self.end_event.is_set():
            if isinstance(item, str):
                self.token_count += len(item)
            self.queue.put(item)

    def end_iteration(self):
        """Signal that no more items will be added."""
        self.end_event.set()
        self.queue.put(None)
        print("Generator exit requested...")

    def __iter__(self):
        """Make this object an iterable."""
        while not self.end_event.is_set():
            try:
                item = self.queue.get(timeout=0.1)  # Using a timeout to periodically check the end_event
                if item is None:
                    self.queue.put(None)
                    break
                yield item
            except queue.Empty:
                continue

        #Once we have set the end_event, we simply yield all the remaining text chunks before exiting.
        while True:
            item = self.queue.get()
            if item is None:
                break
            yield item
        print("Generator exited.")


    def is_ended(self):
        """Check if the end iteration signal has been set."""
        return self.end_event.is_set()

user = ElevenLabsUser(xi_api_key)
voice = user.get_available_voices()[0]

current_generator = SharedGenerator()
input_streamer = ReusableInputStreamer(voice, generationOptions=GenerationOptions(model="eleven_turbo_v2"))
input_streamer.queue_audio(current_generator)

token_max = user.get_model_by_id("eleven_turbo_v2").maxCharacters
def main():
    try:
        # example of setting up a client config. logging values: WARNING, VERBOSE, DEBUG, SPAM
        # config = DeepgramClientOptions(
        #     verbose=logging.DEBUG,
        #     options={"keepalive": "true"}
        # )
        # deepgram: DeepgramClient = DeepgramClient("", config)
        # otherwise, use default config


        config = DeepgramClientOptions(
            api_key=dg_api_key,
            options={"keepalive": "true"}
        )
        deepgram = DeepgramClient(config=config)

        dg_connection = deepgram.listen.live.v("1")

        def on_message(self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return  #Outright ignore ones with no text

            #This is where we can mark the user as starting to speak.

            print(sentence)
            global current_generator

            if result.is_final and not result.speech_final:
                print("is_final but not speech_final")
                print("Sending.")
                #Send it.
                current_generator.add_item(sentence + " ")


            if result.speech_final:
                print("speech_final")
                #Send it with a flush.
                print("Sending with flush.")
                current_generator.add_item({"text":sentence + " ", "flush":True})
                if current_generator.token_count > (token_max/2):
                    print("Over half the possible tokens. Let's switch it up.")
                    current_generator.end_iteration()
                    #Create a new instance and queue it up.
                    current_generator = SharedGenerator()
                    input_streamer.queue_audio(current_generator)

            print("")
            #print(result)

            #print(f"speaker: {sentence}")


        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        options = LiveOptions(
            #punctuate=True,
            language="en",
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            smart_format=True,
            interim_results=True,
            endpointing="500",
            model="nova-2",
            vad_events=True
        )
        dg_connection.start(options, addons=dict(myattr="hello"), test="hello")

        # Open a microphone stream on the default input device
        microphone = Microphone(dg_connection.send)

        # start microphone
        microphone.start()

        # wait until finished
        input("Press Enter to stop recording...\n\n")

        # Wait for the microphone to close
        microphone.finish()

        # Indicate that we've finished
        dg_connection.finish()

        print("Finished")
        # sleep(30)  # wait 30 seconds to see if there is any additional socket activity
        # print("Really done!")

    except Exception as e:
        print(f"Could not open socket: {e}")
        return


if __name__ == "__main__":
    main()
