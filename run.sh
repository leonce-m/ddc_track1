python3 dronebot/mic_vad_streaming.py \
-m models/deepspeech-0.9.3-models.pbmm \
-s models/srs3.scorer \
-d "$1" -r 44100 -k
python3 -m dronebot.controller -s 'serial:///dev/serial0:921600'
