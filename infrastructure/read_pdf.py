from pdfminer.high_level import extract_text
text = extract_text('.user_uploaded/Profile (7).pdf')
with open('profile_text.txt', 'w', encoding='utf-8') as f:
    f.write(text)
print("Saved full text to profile_text.txt")
