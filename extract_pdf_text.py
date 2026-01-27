import zlib
import re

def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as f:
        content = f.read()

    # Find all streams
    streams = re.findall(b'stream[\r\n]+(.*?)[\r\n]+endstream', content, re.DOTALL)
    
    extracted_text = []
    
    for stream in streams:
        try:
            decompressed = zlib.decompress(stream)
            # Try to decode as utf-8, ignore errors
            text = decompressed.decode('utf-8', errors='ignore')
            # Extract text within parentheses (...)
            text_parts = re.findall(r'\((.*?)\)', text)
            extracted_text.extend(text_parts)
        except Exception:
            pass
            
    return "\n".join(extracted_text)

if __name__ == "__main__":
    print(extract_text_from_pdf("chimera.pdf"))
