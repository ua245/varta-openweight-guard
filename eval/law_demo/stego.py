"""Explicit PNG RGB LSB codec. This is concealment, not encryption or source authentication."""
import hashlib
import struct
from pathlib import Path
from PIL import Image

MAGIC=b'STEG\x01'
LIMIT=16000


def embed(cover,output,text):
    payload=text.encode('utf-8')
    if len(payload)>LIMIT:raise ValueError('Payload too large')
    frame=MAGIC+struct.pack('>I',len(payload))+hashlib.sha256(payload).digest()+payload
    image=Image.open(cover).convert('RGB');pixels=bytearray(image.tobytes())
    if len(frame)*8>len(pixels):raise ValueError('Cover image capacity exceeded')
    for index,byte in enumerate(frame):
        for bit in range(8):
            j=index*8+bit;pixels[j]=(pixels[j]&254)|((byte>>(7-bit))&1)
    Image.frombytes('RGB',image.size,bytes(pixels)).save(output,format='PNG')
    return {'codec':'RGB-LSB / STEG-v1 / SHA256 integrity','payload_bytes':len(payload),
            'payload_sha256':hashlib.sha256(payload).hexdigest(),
            'image_sha256':hashlib.sha256(Path(output).read_bytes()).hexdigest()}


def extract(path):
    image=Image.open(path)
    if image.width*image.height>4000000:raise ValueError('Image exceeds decoder limit')
    pixels=image.convert('RGB').tobytes()
    def read(n):
        if n*8>len(pixels):raise ValueError('Truncated LSB data')
        return bytes(sum((pixels[i*8+j]&1)<<(7-j) for j in range(8)) for i in range(n))
    if len(pixels)<72:return None
    header=read(9)
    if header[:5]!=MAGIC:return None
    length=struct.unpack('>I',header[5:9])[0]
    if length>LIMIT:raise ValueError('Invalid hidden payload length')
    frame=read(41+length);payload=frame[41:]
    if hashlib.sha256(payload).digest()!=frame[9:41]:raise ValueError('Hidden payload checksum mismatch')
    return payload.decode('utf-8')
