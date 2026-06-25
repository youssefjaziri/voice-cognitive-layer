"""
orlock_api_client.py
--------------------
HTTP client to send audio to Orlock server with intelligent orchestration support.
"""

import io
import json
import requests
import numpy as np
import soundfile as sf
from typing import Optional, Dict, Any


class OrlockAPIClient:
    """Send audio to Orlock server with metadata support."""

    def __init__(self, server_url: str = "http://localhost:8000", use_orchestrated: bool = True):
        self.server_url = server_url
        self.use_orchestrated = use_orchestrated
        self.endpoint = f"{server_url}/api/v1/{'orchestrated/audio' if use_orchestrated else 'userAudio'}"

    def send_audio(
        self,
        audio_data: np.ndarray,
        user_id: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        sample_rate: int = 16000,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """
        Send audio buffer to Orlock server with optional metadata.

        Args:
            audio_data: numpy array of audio samples (float32 normalized to [-1, 1])
            user_id: user identifier
            system: optional system prompt
            temperature: LLM temperature (default 0.2)
            sample_rate: sample rate (default 16000 Hz)
            metadata: optional dict with VAD confidence, speech duration, silence duration, etc.

        Returns:
            dict with response from server, or error info
        """
        try:
            # Convert numpy array to WAV bytes
            wav_buffer = io.BytesIO()
            sf.write(wav_buffer, audio_data, sample_rate, format='WAV')
            wav_buffer.seek(0)

            # Prepare form data
            files = {'audio': ('segment.wav', wav_buffer, 'audio/wav')}
            data = {'user_id': user_id}

            # Add metadata if using orchestrated endpoint
            if self.use_orchestrated and metadata:
                metadata_json = json.dumps(metadata)
                data['metadata_json'] = metadata_json

            # Add optional parameters
            if system:
                data['system_prompt'] = system

            # Send to Orlock API
            response = requests.post(
                self.endpoint,
                files=files,
                data=data,
                timeout=180,
            )
            response.raise_for_status()

            return {
                'success': True,
                'status_code': response.status_code,
                'response': response.json(),
            }

        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': f'Could not connect to {self.endpoint}',
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout',
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }

    def send_orchestrated_text(
        self,
        text: str,
        user_id: str,
        system: Optional[str] = None,
    ) -> dict:
        """
        Send text message to orchestrated endpoint for intent-aware response.

        Args:
            text: user text input
            user_id: user identifier
            system: optional system prompt

        Returns:
            dict with response from server, or error info
        """
        try:
            endpoint = f"{self.server_url}/api/v1/orchestrated/message"

            payload = {
                'user_id': user_id,
                'text': text,
            }
            if system:
                payload['system_prompt'] = system

            response = requests.post(
                endpoint,
                json=payload,
                timeout=180,
            )
            response.raise_for_status()

            return {
                'success': True,
                'status_code': response.status_code,
                'response': response.json(),
            }

        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': f'Could not connect to orchestrated endpoint',
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout',
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
