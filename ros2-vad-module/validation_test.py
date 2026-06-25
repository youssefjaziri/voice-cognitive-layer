#!/usr/bin/env python3
"""
validation_test.py
--------------------
Quick validation that all components are in place.
Run this to verify the integration is correct.
"""

import sys
import os

def check_file_exists(path, name):
    """Check if a file exists."""
    if os.path.exists(path):
        print(f"✓ {name}: {path}")
        return True
    else:
        print(f"✗ {name}: NOT FOUND - {path}")
        return False

def check_imports():
    """Try to import the API client."""
    try:
        from vad_component.orlock_api_client import OrlockAPIClient
        print("✓ OrlockAPIClient: Import OK")
        return True
    except ImportError as e:
        print(f"✗ OrlockAPIClient: Import FAILED - {e}")
        return False

def check_file_content(path, search_string, name):
    """Check if a file contains specific content."""
    try:
        with open(path, 'r') as f:
            content = f.read()
            if search_string in content:
                print(f"✓ {name}: Found in file")
                return True
            else:
                print(f"✗ {name}: NOT found in file")
                return False
    except Exception as e:
        print(f"✗ {name}: Error reading file - {e}")
        return False

def main():
    """Run all validation checks."""
    print("=" * 60)
    print("VALIDATION TEST - Orlock API Integration")
    print("=" * 60)

    results = []

    print("\n1. FILES CHECK")
    print("-" * 60)
    results.append(check_file_exists(
        'src/vad_component/vad_component/orlock_api_client.py',
        'API Client Module'
    ))
    results.append(check_file_exists(
        'src/vad_component/vad_component/speech_segmentation_node.py',
        'Speech Segmentation Node'
    ))
    results.append(check_file_exists(
        'requirements.txt',
        'Requirements File'
    ))

    print("\n2. IMPORTS CHECK")
    print("-" * 60)
    results.append(check_imports())

    print("\n3. DEPENDENCIES CHECK")
    print("-" * 60)
    results.append(check_file_content(
        'requirements.txt',
        'requests>=2.31.0',
        'requests library'
    ))
    results.append(check_file_content(
        'src/vad_component/setup.py',
        "'requests'",
        'requests in setup.py'
    ))

    print("\n4. CODE INTEGRATION CHECK")
    print("-" * 60)
    results.append(check_file_content(
        'src/vad_component/vad_component/speech_segmentation_node.py',
        'from vad_component.orlock_api_client import OrlockAPIClient',
        'API imports'
    ))
    results.append(check_file_content(
        'src/vad_component/vad_component/speech_segmentation_node.py',
        'enable_api',
        'API parameter declaration'
    ))
    results.append(check_file_content(
        'src/vad_component/vad_component/speech_segmentation_node.py',
        '_send_to_api',
        'API send method'
    ))
    results.append(check_file_content(
        'src/vad_component/vad_component/speech_segmentation_node.py',
        'self._send_to_api(audio_data)',
        'API call in _save_segment'
    ))

    print("\n5. DOCUMENTATION CHECK")
    print("-" * 60)
    results.append(check_file_exists(
        'ORLOCK_API_INTEGRATION.md',
        'Integration Guide'
    ))
    results.append(check_file_exists(
        'IMPLEMENTATION_SUMMARY.md',
        'Implementation Summary'
    ))
    results.append(check_file_exists(
        'TESTING_GUIDE.md',
        'Testing Guide'
    ))

    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} checks passed")
    print("=" * 60)

    if passed == total:
        print("\n✓ ALL CHECKS PASSED - Integration is ready!")
        return 0
    else:
        print(f"\n✗ {total - passed} checks failed - Review errors above")
        return 1

if __name__ == '__main__':
    sys.exit(main())
