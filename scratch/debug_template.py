import requests

s = requests.Session()
s.post('https://cardioqueue-production.up.railway.app/opd/login', data={'pin': '1234'}, allow_redirects=True)
r = s.get('https://cardioqueue-production.up.railway.app/opd/dashboard')

text = r.text
print("Raw string length:", len(text))
print("'camera-file-input' in text?:", "camera-file-input" in text)
print("'Camera Snap' in text?:", "Camera Snap" in text)
print("'Gallery Upload' in text?:", "Gallery Upload" in text)

# Find where 'New Prescription' is located
pos = text.find("New Prescription")
print("Position of 'New Prescription':", pos)
if pos != -1:
    snippet = text[pos-100:pos+1500]
    with open("scratch/live_snippet.txt", "w", encoding="utf-8") as f:
        f.write(snippet)
    print("Wrote snippet around New Prescription to scratch/live_snippet.txt")
