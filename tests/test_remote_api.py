import urllib.request
import json
import time

url = 'https://localhost.scode.web.id/2026-tiara-tomat/api/klasifikasi.php'
boundary = f'----WebKitFormBoundary{int(time.time())}'
parts = []

def add_field(k, v):
    parts.append(f'--{boundary}\r\n'.encode('utf-8'))
    parts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode('utf-8'))
    parts.append(f'{v}\r\n'.encode('utf-8'))

import numpy as np
import cv2

add_field('jenis', 'Setengah Matang')
add_field('confidence', '88.0')
add_field('metode', 'C4.5 HSV')
add_field('fitur', 'H: 25.0, S: 150.0, V: 190.0')

# Generate dummy tomato image
img = np.zeros((120, 120, 3), dtype=np.uint8)
img[:, :] = (0, 165, 255) # Orange BGR
_, buf = cv2.imencode('.jpg', img)

parts.append(f'--{boundary}\r\n'.encode('utf-8'))
parts.append(b'Content-Disposition: form-data; name="foto"; filename="test_tomat.jpg"\r\n')
parts.append(b'Content-Type: image/jpeg\r\n\r\n')
parts.append(buf.tobytes())
parts.append(b'\r\n')
parts.append(f'--{boundary}--\r\n'.encode('utf-8'))
data = b''.join(parts)

req = urllib.request.Request(url, data=data, headers={
    'Content-Type': f'multipart/form-data; boundary={boundary}',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Tomata-IoT/1.0',
    'Connection': 'close'
}, method='POST')

try:
    with urllib.request.urlopen(req, timeout=12) as resp:
        print('Status Code:', resp.status)
        print('Response Body:', resp.read().decode('utf-8'))
except urllib.error.HTTPError as he:
    print('HTTP Error:', he.code, he.read().decode('utf-8', errors='ignore'))
except Exception as e:
    print('Error:', e)
