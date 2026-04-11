#!/usr/bin/env python3
"""Generate placeholder WAV sound files for DogBuddy. Run from project root."""

import os
import math
import struct
import wave

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'renderer', 'public', 'sounds')

def generate_sine_wave(freq=440, duration=0.5, sample_rate=44100, amplitude=0.4):
    num_samples = int(sample_rate * duration)
    samples = [int(amplitude * math.sin(2 * math.pi * freq * i / sample_rate) * 32767)
               for i in range(num_samples)]
    return struct.pack(f'<{num_samples}h', *samples)

def write_wav(filename, freq=440, duration=0.5, sample_rate=44100):
    path = os.path.join(OUTPUT_DIR, filename)
    with wave.open(path, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(generate_sine_wave(freq, duration, sample_rate))
    print(f'Generated: {path}')

os.makedirs(OUTPUT_DIR, exist_ok=True)
write_wav('bark_short.wav',    freq=800, duration=0.3)
write_wav('bark_happy.wav',    freq=600, duration=0.6)
write_wav('whine.wav',         freq=400, duration=0.8)
write_wav('notification.wav',  freq=523, duration=0.5)
print('Done.')
