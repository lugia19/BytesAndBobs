#Using emotional classification to add appropriate prompting
import keyring
from huggingface_hub import InferenceClient
from elevenlabslib import *

client = InferenceClient()

xi_api_key = keyring.get_password("bytes_and_bobs", "elevenlabs_api_key")
user = ElevenLabsUser(xi_api_key)
voice = user.get_voices_by_name_v2("Fin")[0]
#Low stability = more expression
generation_options = GenerationOptions(stability=0.1)


emotion_cues = {
    'anger': "he said angrily",
    'disgust': "he said with disgust",
    'fear': "he said fearfully",
    'joy': "he said joyfully",
    'sadness': "he said sadly",
    'surprise': "he said, surprised"
}
def get_emotion_cue(text):
    # Get the most likely emotion
    results = client.text_classification(text, model='j-hartmann/emotion-english-distilroberta-base')
    emotion = results[0]['label'].lower()

    return emotion_cues.get(emotion) + "."




if __name__=="__main__":
    input_text = "What are you doing here?"
    cue = get_emotion_cue(input_text)
    print(f"Without prompting: {input_text}")
    voice.generate_stream_audio_v2(input_text, generationOptions=generation_options)
    print(f'With prompting: "{input_text}" {cue}')
    voice.generate_stream_audio_v2(input_text, generationOptions=generation_options, promptingOptions=PromptingOptions(post_prompt=cue))