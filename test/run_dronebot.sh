# source venv/bin/activate
mplayer 'http://192.168.8.222:8000/ddc' &
sleep 10
python3 dronebot/mic_vad_streaming.py \
-m models/srs.pb -s models/srs.scorer \
-r 44100 -v 0 --nospinner | \
python3 -m dronebot.controller -v & \
# aplay '20201014 165538.m4a'