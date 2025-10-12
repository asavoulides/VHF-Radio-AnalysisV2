import sys
sys.path.append(r"c:\Users\alexa\OneDrive\Desktop\Folders\Scripts\Python\Local Police Scanner Analysis")

import incident_helper

# Test with real longer transcripts that are still "unknown"
test_transcripts = [
    "Sir, can you start us Quilley's Towing? We're at Rivea, Route 16 East at the Kroner Rink.",  # 17 words - towing
    "Sir, can you go again with that? You said that they are still in the car? Yeah. Apparently, they're in trap.",  # 21 words
    "Sir, gonna stay at that vehicle with Alkinson. I'll be 17.",  # 11 words - traffic stop
    "4, we'll head that way. Cancel 2. Roger. I have it. Thank you for",  # 14 words
]

print("\n" + "="*80)
print("TESTING CLASSIFICATION ON LONGER TRANSCRIPTS")
print("="*80 + "\n")

for i, transcript in enumerate(test_transcripts, 1):
    word_count = len(transcript.split())
    print(f"Test {i} ({word_count} words): {transcript}")
    try:
        result = incident_helper.classify_incident(transcript)
        print(f"  ✓ Result: {result}")
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    print("-" * 80)
