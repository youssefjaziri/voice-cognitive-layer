#!/usr/bin/env python3
"""
end_to_end_test.py
-------------------
Test the full integration loop without ROS2.
Simulates: Audio capture → API send → LLM response
"""

import numpy as np
import sys
from pathlib import Path

def test_api_client():
    """Test API client with dummy audio."""
    print("=" * 60)
    print("END-TO-END API TEST (without ROS2)")
    print("=" * 60)

    try:
        from vad_component.orlock_api_client import OrlockAPIClient
        print("\n✓ Step 1: Import OrlockAPIClient - OK")
    except ImportError as e:
        print(f"\n✗ Step 1: Import FAILED - {e}")
        return False

    # Create client
    try:
        client = OrlockAPIClient("http://localhost:8000")
        print("✓ Step 2: Create OrlockAPIClient - OK")
    except Exception as e:
        print(f"✗ Step 2: Create client FAILED - {e}")
        return False

    # Create dummy audio (1 second of sine wave)
    try:
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
        print(f"✓ Step 3: Create dummy audio - {len(audio)} samples")
    except Exception as e:
        print(f"✗ Step 3: Create audio FAILED - {e}")
        return False

    # Send to API
    try:
        print("\n→ Sending audio to Orlock server at http://localhost:8000/api/v1/userAudio")
        response = client.send_audio(
            audio_data=audio,
            user_id="test_user",
            system=None,
            sample_rate=sample_rate,
        )
        print("✓ Step 4: Send audio - Request completed")
    except Exception as e:
        print(f"✗ Step 4: Send audio FAILED - {e}")
        return False

    # Check response
    try:
        if response['success']:
            print(f"✓ Step 5: API Response - SUCCESS")
            print(f"  Status Code: {response['status_code']}")
            print(f"  Response Data:")
            resp_data = response.get('response', {})
            print(f"    user_id: {resp_data.get('user_id')}")
            print(f"    user_text: {resp_data.get('user_text', 'N/A')[:80]}")
            print(f"    llm_response: {resp_data.get('llm_response', 'N/A')[:80]}")
            return True
        else:
            print(f"✗ Step 5: API Response - FAILED")
            print(f"  Error: {response.get('error')}")
            return False
    except Exception as e:
        print(f"✗ Step 5: Parse response FAILED - {e}")
        return False

if __name__ == '__main__':
    print("\nRun this to test API connectivity without ROS2")
    print("Make sure Orlock server is running on http://localhost:8000\n")

    success = test_api_client()

    print("\n" + "=" * 60)
    if success:
        print("✓ END-TO-END TEST PASSED")
        print("=" * 60)
        sys.exit(0)
    else:
        print("✗ END-TO-END TEST FAILED")
        print("=" * 60)
        sys.exit(1)
