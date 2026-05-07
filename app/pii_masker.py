import re

def mask_pii(text: str) -> str:
    """
    Masks Indian PII data from the input text using Regex.
    Ensures that Aadhaar, PAN, and Phone numbers are not sent to the LLM.
    """
    if not text:
        return text

    # 1. Mask Indian Phone Numbers (e.g., +91 9876543210, 9876543210)
    phone_pattern = r'(\+91[\-\s]?)?[6789]\d{9}'
    text = re.sub(phone_pattern, '[MASKED_PHONE]', text)

    # 2. Mask Aadhaar Card Numbers (e.g., 1234 5678 9012 or 123456789012)
    aadhaar_pattern = r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b'
    text = re.sub(aadhaar_pattern, '[MASKED_AADHAAR]', text)

    # 3. Mask PAN Card Numbers (e.g., ABCDE1234F)
    pan_pattern = r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b'
    text = re.sub(pan_pattern, '[MASKED_PAN]', text)

    return text
