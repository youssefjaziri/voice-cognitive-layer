from setuptools import find_packages, setup

package_name = 'vad_component'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/guida.launch.py']),
    ],
    install_requires=[
        'setuptools',
        'numpy',
        'soundfile',
        'sounddevice',
        'torch',
        'silero-vad',
        'faster-whisper',
        'requests',
    ],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='you@example.com',
    description='VAD component: fake mic + Silero VAD nodes',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # Fake microphone node (testing with a .wav file)
            'fake_mic_node = vad_component.fake_mic_node:main',
            # Real microphone node (live capture via sounddevice)
            'mic_node = vad_component.mic_node:main',
            # VAD node (uses Silero VAD to detect speech)
            'vad_node = vad_component.vad_node:main',
            # Speech segmentation node (saves speech segments to .wav files)
            'speech_segmentation_node = vad_component.speech_segmentation_node:main',
            # TTS node (speaks LLM responses aloud via /orlock/response topic)
            'tts_node = vad_component.tts_node:main',
        ],
    },
)
