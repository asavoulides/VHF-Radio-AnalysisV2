import os
import re
from dotenv import load_dotenv
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from openai import OpenAI
from utils import getPrompt
import location_services
# Load environment variables from .env file
import os as _os
script_dir = _os.path.dirname(_os.path.abspath(__file__))
env_path = _os.path.join(script_dir, '.env')
load_dotenv(env_path)

# Get the API key from the environment
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
if not DEEPGRAM_API_KEY:
    print("ERROR: DEEPGRAM_API_KEY not found in environment variables!")
    print(f"Looking for .env file at: {env_path}")
    print(f".env file exists: {_os.path.exists(env_path)}")

# Address extraction patterns
ADDRESS_PATTERNS = [
    # Standard street addresses: "123 Main Street", "456 Oak Ave", etc.
    r"\b(\d{1,5})\s+([A-Za-z\s]{2,30}?)\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Boulevard|Blvd|Place|Pl|Way|Terrace|Ter)\b",
    # Addresses with apartment/unit numbers: "123 Main St Apartment 5", "456 Oak Ave Unit 2B"
    r"\b(\d{1,5})\s+([A-Za-z\s]{2,30}?)\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Boulevard|Blvd|Place|Pl|Way|Terrace|Ter)\s*(?:,?\s*(?:Apartment|Apt|Unit|#)\s*(?:Number\s*)?(\w+))?\b",
    # Highway/Route addresses: "Route 95", "Highway 1", "I-495"
    r"\b(?:Route|Rt|Highway|Hwy|Interstate|I-?)\s*(\d{1,3}[A-Z]?)\b",
    # Intersection format: "Main Street and Oak Avenue", "Beacon St at Washington St"
    r"\b([A-Za-z\s]{2,20}?)\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Boulevard|Blvd|Place|Pl|Way|Terrace|Ter)\s+(?:and|at|&)\s+([A-Za-z\s]{2,20}?)\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Boulevard|Blvd|Place|Pl|Way|Terrace|Ter)\b",
    # Business addresses with street numbers: "123 Washington Street, the Target"
    r"\b(\d{1,5})\s+([A-Za-z\s]{2,30}?)\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Boulevard|Blvd|Place|Pl|Way|Terrace|Ter)(?:,\s*(?:the\s+)?([A-Za-z\s&\'\-]{2,30}))?\b",
    # School/facility addresses: "Oak Hill School, 130 Wheeler Road"
    r"\b([A-Za-z\s]{2,30}?(?:School|Hospital|Center|Building|Plaza|Mall|Park)),?\s+(\d{1,5})\s+([A-Za-z\s]{2,30}?)\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Boulevard|Blvd|Place|Pl|Way|Terrace|Ter)\b",
]


def extract_address(transcript):
    """Extract address information from transcript content"""
    if not transcript or not transcript.strip():
        return None

    # Clean up the transcript - remove extra spaces and normalize
    text = re.sub(r"\s+", " ", transcript.strip())

    addresses = []

    # Try each address pattern
    for pattern in ADDRESS_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            # Handle different pattern types
            if "and|at|&" in pattern:  # Intersection pattern
                street1 = f"{match.group(1).strip()} {match.group(2)}"
                street2 = f"{match.group(3).strip()} {match.group(4)}"
                address = f"{street1} and {street2}"
            elif "Route|Rt|Highway" in pattern:  # Highway pattern
                address = f"{match.group(0)}"
            elif "School|Hospital|Center" in pattern:  # Facility pattern
                facility = match.group(1).strip()
                number = match.group(2)
                street = match.group(3).strip()
                suffix = match.group(4)
                address = f"{facility}, {number} {street} {suffix}"
            else:  # Standard street address
                groups = match.groups()
                if len(groups) >= 3:
                    number = groups[0]
                    street = groups[1].strip()
                    suffix = groups[2]

                    # Handle apartment/unit if present
                    if len(groups) > 3 and groups[3]:
                        address = f"{number} {street} {suffix} #{groups[3]}"
                    else:
                        address = f"{number} {street} {suffix}"
                else:
                    continue

            # Clean up the address
            address = re.sub(r"\s+", " ", address.strip())

            # Avoid duplicates and very short addresses
            if len(address) > 5 and address not in addresses:
                addresses.append(address)

    # Return the most specific address (usually the longest one)
    if addresses:
        # Sort by length and specificity, prefer numbered addresses
        addresses.sort(key=lambda x: (len(x), bool(re.match(r"^\d", x))), reverse=True)
        return addresses[0]

    return None





def normalize_police_codes(transcript):
    """Normalize spaced police codes to proper format"""
    # Pattern to match spaced numbers - handles both "4 91" and "49 1" formats
    patterns = [
        # Handle "4 9X" patterns (like "4 91", "4 92", etc.)
        (r"\b4\s+9\s*1\b", "491"),
        (r"\b4\s+9\s*2\b", "492"),
        (r"\b4\s+9\s*3\b", "493"),
        (r"\b4\s+9\s*4\b", "494"),
        (r"\b4\s+9\s*5\b", "495"),
        (r"\b4\s+9\s*6\b", "496"),
        (r"\b4\s+9\s*7\b", "497"),
        (r"\b4\s+9\s*8\b", "498"),
        (r"\b4\s+9\s*9\b", "499"),
        # Handle "49 X" patterns (like "49 1", "49 2", etc.)
        (r"\b49\s+1\b", "491"),
        (r"\b49\s+2\b", "492"),
        (r"\b49\s+3\b", "493"),
        (r"\b49\s+4\b", "494"),
        (r"\b49\s+5\b", "495"),
        (r"\b49\s+6\b", "496"),
        (r"\b49\s+7\b", "497"),
        (r"\b49\s+8\b", "498"),
        (r"\b49\s+9\b", "499"),
        # Handle "5 0X" patterns (like "5 01", "5 02", etc.)
        (r"\b5\s+0\s*0\b", "500"),
        (r"\b5\s+0\s*1\b", "501"),
        (r"\b5\s+0\s*2\b", "502"),
        (r"\b5\s+0\s*3\b", "503"),
        (r"\b5\s+0\s*4\b", "504"),
        # Handle "50 X" patterns (like "50 0", "50 1", etc.)
        (r"\b50\s+0\b", "500"),
        (r"\b50\s+1\b", "501"),
        (r"\b50\s+2\b", "502"),
        (r"\b50\s+3\b", "503"),
        (r"\b50\s+4\b", "504"),
        # Handle "4nine XX" patterns (where XX represents last two digits)
        (r"\b4nine\s+30\b", "493"),
        (r"\b4nine\s+40\b", "494"),
        (r"\b4nine\s+50\b", "495"),
        (r"\b4nine\s+60\b", "496"),
        (r"\b4nine\s+70\b", "497"),
        (r"\b4nine\s+80\b", "498"),
        (r"\b4nine\s+90\b", "499"),
        # Handle written forms
        (r"\bfour\s+nine\s+one\b", "491"),
        (r"\bfour\s+nine\s+two\b", "492"),
        (r"\bfour\s+nine\s+three\b", "493"),
        (r"\bfour\s+nine\s+four\b", "494"),
        (r"\bfour\s+nine\s+five\b", "495"),
        (r"\bfour\s+nine\s+six\b", "496"),
        (r"\bfour\s+nine\s+seven\b", "497"),
        (r"\bfour\s+nine\s+eight\b", "498"),
        (r"\bfour\s+nine\s+nine\b", "499"),
        (r"\bfive\s+zero\s+zero\b", "500"),
        (r"\bfive\s+zero\s+one\b", "501"),
        (r"\bfive\s+zero\s+two\b", "502"),
        (r"\bfive\s+zero\s+three\b", "503"),
        (r"\bfive\s+zero\s+four\b", "504"),
        # Handle "four nine" without the third digit
        (r"\b4\s+nine\s+(\d)\b", r"49\1"),
    ]

    normalized_transcript = transcript
    for pattern, replacement in patterns:
        normalized_transcript = re.sub(
            pattern, replacement, normalized_transcript, flags=re.IGNORECASE
        )

    return normalized_transcript


def getTranscript(audioPath):
    try:
        # Verify file exists before processing
        if not _os.path.exists(audioPath):
            print(f"ERROR: File does not exist: {audioPath}")
            return None
        
        if not _os.path.isfile(audioPath):
            print(f"ERROR: Path is not a file: {audioPath}")
            return None
            
        file_size = _os.path.getsize(audioPath)
        if file_size == 0:
            print(f"ERROR: File is empty: {audioPath}")
            return None
        
        print(f"[Debug] Processing file: {audioPath} (size: {file_size} bytes)")
        
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
                "491",
                "492",
                "493",
                "494",
                "495",
                "496",
                "497",
                "498",
                "499",
                "500",
                "501",
                "502",
                "503",
                "504",
                "control",
            ],
        )

        response = deepgram.listen.rest.v("1").transcribe_file(payload, options)

        # Extract transcript and confidence
        result = response["results"]["channels"][0]["alternatives"][0]
        transcript = result["transcript"]

        # Get confidence score - handle both dict and object response formats
        try:
            confidence = (
                result["confidence"]
                if isinstance(result, dict)
                else getattr(result, "confidence", 0.0)
            )
        except (KeyError, AttributeError):
            confidence = 0.0

        # Apply police code normalization
        normalized_transcript = normalize_police_codes(transcript)

        # Classify incident type based on the normalized transcript

        # Extract address information
        address = location_services.normalize_address(normalized_transcript)

        return {
            "transcript": normalized_transcript,
            "confidence": confidence,
            "address": address,
        }

    except Exception as e:
        import traceback
        print(f"Exception in getTranscript for {audioPath}: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return None


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
