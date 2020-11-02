cd ./dev
python3 mic_vad_streaming.py -m ../models/deepspeech-0.8.2-models.pbmm -d "$1" -r 44100 -k
python3 voice_ctrl_sys.py
