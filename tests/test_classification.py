import sys
sys.path.append(r"c:\Users\alexa\OneDrive\Desktop\Folders\Scripts\Python\Local Police Scanner Analysis")

import incident_helper

# Test with some real transcripts from the database
test_transcripts = [
    "Party sign and refusing. You can show me clear. Roger.",
    "2206.",
    "One 3981.",
    "498 to control.",
    "4ninety 8, control. Control.",
]

print("\n" + "="*80)
print("TESTING INCIDENT CLASSIFICATION")
print("="*80 + "\n")

for i, transcript in enumerate(test_transcripts, 1):
    print(f"Test {i}: {transcript}")
    try:
        result = incident_helper.classify_incident(transcript)
        print(f"  ✓ Result: {result}")
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    print("-" * 80)
