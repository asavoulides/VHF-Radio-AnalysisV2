import os
from dotenv import load_dotenv
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# Path to the audio file
# AUDIO_FILE = r"C:\ProScan\Recordings\04-13-25\Middlesex\04-13-25 00-08-11 - Middlesex - Police Department.mp3"


def getPrompt(promptName):
    with open(f"Prompts/{promptName}", "r", encoding="utf-8") as file:
        return file.read()

def getTranscript(AUDIO_FILE):
    try:
        # Create Deepgram client using the API key
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)

        with open(AUDIO_FILE, "rb") as file:
            buffer_data = file.read()

        payload: FileSource = {
            "buffer": buffer_data,
        }

        options = PrerecordedOptions(
            model="nova-3",
            smart_format=True,
        )

        response = deepgram.listen.rest.v("1").transcribe_file(payload, options)

        # Extract just the transcript text
        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]

        return transcript

    except Exception as e:
        print(f"Exception: {e}")


def LLM_REQ(text):
    client = OpenAI()

    response = client.responses.create(
        model="gpt-4o",
        input=[
            {
            "role": "system",
            "content": [{"type": "input_text", "text": "You are an analyser"}],
            },

            {"role": "user", 
             "content": [{"type": "input_text", "text": text}]},
        ],
        text={"format": {"type": "text"}},
        reasoning={},
        tools=[],
        temperature=1,
        max_output_tokens=2048,
        top_p=1,
        store=True,
    )
    return response.output[0].content[0].text


