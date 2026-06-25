FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace/ros2-VAD-module

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    espeak-ng \
    ffmpeg \
    libsndfile1 \
    portaudio19-dev \
    python3-colcon-common-extensions \
    python3-pip \
    ros-humble-std-msgs \
    && rm -rf /var/lib/apt/lists/*

# Set USB audio (card 1) as the ALSA default for output
RUN printf 'pcm.!default {\n    type plug\n    slave.pcm "hw:1,0"\n}\nctl.!default {\n    type hw\n    card 1\n}\n' > /etc/asound.conf

RUN python3 -m pip install --upgrade pip

COPY requirements.txt ./requirements.txt
RUN python3 -m pip install -r requirements.txt

COPY src ./src

RUN bash -lc "source /opt/ros/humble/setup.bash && colcon build --symlink-install"

CMD ["bash", "-lc", "source /opt/ros/humble/setup.bash && source install/setup.bash && { ros2 run vad_component mic_node --ros-args -p device:=USB & ros2 run vad_component vad_node & ros2 run vad_component tts_node & exec ros2 run vad_component speech_segmentation_node --ros-args -p enable_api:=true -p api_url:=http://orlock:8000 -p api_user_id:=docker_user -p output_dir:=/workspace/ros2-VAD-module/audio_chunks; }"]