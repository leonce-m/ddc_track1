cd ./dev
chmod +x mic_vad_streaming.py
chmod +x voice_ctrl_sys.py
./mic_vad_streaming.py -m ../models/deepspeech-0.8.1-models.pbmm -d "$1" -r 44100 -k
./voice_ctrl_sys.py
