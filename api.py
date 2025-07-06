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
            keyterm=[
                # General Law Enforcement
                "control",
                "arrest",
                "in custody",
                "officer",
                "suspect",
                "vehicle stop",
                "motor vehicle stop",
                "traffic stop",
                "warrant",
                "bolo",  # Be On the Lookout
                "bop",  # Board of Probation (Massachusetts-specific)
                "one under",  # suspect in custody
                "detained",
                "detain",
                "subject",
                "party",
                "RP",  # reporting party
                "clear the station",
                "en route",
                "scene",
                "backup",
                "request backup",
                "responding",
                "out with",
                "status check",
                "foot pursuit",
                "shots fired",
                "gun",
                "knife",
                "weapon drawn",
                "disorderly",
                "domestic",
                "assault",
                "breaking and entering",
                "robbery",
                "fight",
                "disturbance",
                # EMS/Fire
                "fire",
                "alarm",
                "medic",
                "ems",
                "rescue",
                "transport",
                "injury",
                "burns",
                "conscious",
                "not breathing",
                "unconscious",
                "seizure",
                "code",
                "cardiac",
                "trauma",
                "medical",
                "FS",  # Fire Supervisor / Fire Service
                "box",  # Box alarm
                # Location & Traffic
                "intersection",
                "route",
                "highway",
                "mile marker",
                "northbound",
                "southbound",
                "eastbound",
                "westbound",
                "breakdown lane",
                "off ramp",
                "on ramp",
                "accident",
                "crash",
                "disabled vehicle",
                "DMV",  # Disabled Motor Vehicle
                "tow",
                "tow en route",
                "blocking",
                "closed",
                "closure",
                "divert",
                "Newton",
                "Massachusetts",
                "fire alarm",
                # Dispatch/Radio Specific
                "in the area",
                "cruise",
                "ETA",
                "copy",
                "10-4",
                "received",
                "respond",
                "all set",
                "negative",
                "affirmative",
                "detail",
                "station",
                "units",
                "available",
                "on scene",
                "checking",
                
            ],
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
            "content": [{"type": "input_text", "text": getPrompt("system")}],
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
