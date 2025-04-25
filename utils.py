def getPrompt(promptName):
    with open(f"Prompts/{promptName}", "r", encoding="utf-8") as file:
        return file.read()
