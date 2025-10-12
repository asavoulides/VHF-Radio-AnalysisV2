#!/usr/bin/env python3
"""
Example usage of the ChatGPT Prompter module
"""

from chatgpt_prompter import (
    get_todays_transcripts,
    get_todays_transcripts_by_department,
    save_todays_transcripts_to_file,
    get_gpt_prompt_link,
    open_gpt_prompt_in_browser,
)

print("=" * 60)
print("ChatGPT Prompter - Usage Examples")
print("=" * 60)

# Example 1: Get and print transcripts
print("\n1️⃣  Get formatted transcripts:")
print("-" * 60)
transcripts = get_todays_transcripts()
print(transcripts[:300] + "...\n")  # Show first 300 chars

# Example 2: Get transcripts grouped by department
print("\n2️⃣  Get transcripts by department:")
print("-" * 60)
by_dept = get_todays_transcripts_by_department()
for dept, items in by_dept.items():
    print(f"{dept}: {len(items)} transcripts")

# Example 3: Save to file
print("\n3️⃣  Save transcripts to file:")
print("-" * 60)
result = save_todays_transcripts_to_file()
print(result)

# Example 4: Get ChatGPT link
print("\n4️⃣  Get ChatGPT prompt link:")
print("-" * 60)
link = get_gpt_prompt_link()
if not link.startswith("❌"):
    print(f"Link generated (length: {len(link)} chars)")
    print(f"Link preview: {link[:100]}...")
else:
    print(link)

# Example 5: Open in browser (commented out to avoid auto-opening)
print("\n5️⃣  Open in browser:")
print("-" * 60)
print("To open ChatGPT with today's transcripts, call:")
print("  open_gpt_prompt_in_browser()")
print("\nOr run this script directly:")
print("  python chatgpt_prompter.py")

print("\n" + "=" * 60)
