"""
test_orlock_api_client.py
-------------------------
Simple test for OrlockAPIClient
"""

import numpy as np
from vad_component.orlock_api_client import OrlockAPIClient


def test_api_client():
    """Test the API client with dummy audio."""
    client = OrlockAPIClient("http://localhost:8000")

    # Create dummy audio (1 second at 16kHz)
    sample_rate = 16000
    duration_sec = 1.0
    num_samples = int(sample_rate * duration_sec)

    # Generate simple sine wave
    freq = 440  # A4 note
    t = np.linspace(0, duration_sec, num_samples)
    audio = 0.3 * np.sin(2 * np.pi * freq * t)  # Normalize to [-1, 1]

    print("Testing OrlockAPIClient...")
    print(f"  Audio: {len(audio)} samples at {sample_rate} Hz")
    print(f"  Duration: {len(audio) / sample_rate:.2f}s")

    # Send to API
    response = client.send_audio(
        audio_data=audio,
        user_id="test_user",
        system=None,
        sample_rate=sample_rate,
    )

    print("\nResponse:")
    if response['success']:
        print(f"  ✓ Success! Status: {response['status_code']}")
        print(f"  LLM Response: {response['response'].get('llm_response', 'N/A')}")
    else:
        print(f"  ✗ Error: {response['error']}")

    return response['success']


if __name__ == '__main__':
    success = test_api_client()
    exit(0 if success else 1)
