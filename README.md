# Deep Drone Challenge Track 1
### Prerequisite
#### Mission
Use voice recognition technologies to command a CityAirbus flight from Ingolstadt main station to Munich airport. The CityAirbus is flying autonomously from its departure to its destination and has to communicate with the tower like usual aircrafts, due to a lack of UTM. In doing so, ATC shouldn’t notice any difference in communication compared to a normal aircraft pilot.

#### Challenge
You need to ask for permissions and command take-off, flight, changes during the flight and landing of the drone via voice recognition in real-time. Suddenly appearing external commands, obstacles and conditions will trigger your inner genius to make your drone a master of voice recognition.

#### Mimimum requirements
* Language: English
* Command to adjust flight altitude
* Command to hover/halt
* Command to return to departure
* Identification

#### Additional requirements
* Command to adjust flight route
* Command to adapt to weather changes
* Command change of destination
* Respond and react to local events (e.g. police operation, demonstration etc.)
* Respond and react to crossing traffic
* Command to change in frequency
* Ability to handle noise levels, other languages and dialects
* Variance of Command Deployment
* Speed of responds and action
* Implementation and creativity of own additional capabilities (this is your freestyle)

#### Success factors
* Fly within the given 3-dimensional geofence
* 3 attempts to understand a command
* 5 min in total to solve challenge
* 2 extra min for solving additional requirements
* Completion of 2 successful landings (return to departure, final destination)
* Fly autonomously – use of remote control only as backup solution

#### Setup
* 25x25x25m (w/h/l) 3D airspace to operate in
* Resized props like Tower, Start and Landing Vertiport and other decoration
* Camera drone in the air to overlook the situation
* Live radio module to communicate

## Installation
Clone the repo (duuh):
```
git clone https://github.com/leonce-m/ddc_track1/
```
Uses portaudio for microphone access, so on Linux, you may need to install its header files to compile the `pyaudio` package and install PyAudio using APT instead and `pip` if it's not installed:
```
sudo apt install python3-pyaudio portaudio19-dev python3-pip
```
Then install the rest of the requirements:
```
pip3 install -r dev/requirements.txt
```

## Usage
#### deepspeech
```
  deepspeech --model deepspeech-0.8.2-models.pbmm --scorer deepspeech-0.8.2-models.scorer --audio my_audio_file.wav
```
The --scorer argument is optional, and represents an external language model to be used when transcribing the audio.

#### mic_vad streaming.py
```
usage: python3 mic_vad_streaming.py [-h] [-v VAD_AGGRESSIVENESS] [--nospinner]
                               [-w SAVEWAV] [-f FILE] -m MODEL [-s SCORER]
                               [-d DEVICE] [-r RATE]
   
   Stream from microphone to DeepSpeech using VAD
   
   optional arguments:
     -h, --help            show this help message and exit
     -v VAD_AGGRESSIVENESS, --vad_aggressiveness VAD_AGGRESSIVENESS
                           Set aggressiveness of VAD: an integer between 0 and 3,
                           0 being the least aggressive about filtering out non-
                           speech, 3 the most aggressive. Default: 3
     --nospinner           Disable spinner
     -w SAVEWAV, --savewav SAVEWAV
                           Save .wav files of utterences to given directory
     -f FILE, --file FILE  Read from .wav file instead of microphone
     -m MODEL, --model MODEL
                           Path to the model (protocol buffer binary file, or
                           entire directory containing all standard-named files
                           for model)
     -s SCORER, --scorer SCORER
                           Path to the external scorer file. Default:
                           kenlm.scorer
     -d DEVICE, --device DEVICE
                           Device input index (Int) as listed by
                           pyaudio.PyAudio.get_device_info_by_index(). If not
                           provided, falls back to PyAudio.get_default_device().
     -r RATE, --rate RATE  Input device sample rate. Default: 16000. Your device
                           may require 44100.
     -k, --keyboard        Type output through system keyboards
```
