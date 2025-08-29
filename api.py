import os
from dotenv import load_dotenv
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from openai import OpenAI
from utils import getPrompt

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")


def getTranscript(audioPath):
    try:
        # Create Deepgram client using the API key
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)

        with open(audioPath, "rb") as file:
            buffer_data = file.read()

        payload: FileSource = {
            "buffer": buffer_data,
        }

        options = PrerecordedOptions(
            model="nova-3",
            smart_format=True,
            keyterm=["491", "492", "493", "494", "495", "496","497", "498", "499","500","501","502","503","504","control"]
        )

        response = deepgram.listen.rest.v("1").transcribe_file(payload, options)

        # Extract just the transcript text
        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]

        return transcript

    except Exception as e:
        print(f"Exception: {e}")


def LLM_REQ(text):
    client = OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": getPrompt("system")},
            {"role": "user", "content": text},
        ],
        temperature=1,
        max_tokens=2048,
        top_p=1,
    )

    return response.choices[0].message.content
