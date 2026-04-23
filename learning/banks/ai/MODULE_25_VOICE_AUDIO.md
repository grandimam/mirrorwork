# Module 25: Voice and Audio

## 25.1 Speech-to-Text (Whisper)

```python
from openai import OpenAI

client = OpenAI()

# Transcribe audio file
with open("audio.mp3", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=f
    )
print(transcript.text)

# With options
transcript = client.audio.transcriptions.create(
    model="whisper-1",
    file=open("audio.mp3", "rb"),
    language="en",
    response_format="verbose_json",
    timestamp_granularities=["word"]
)

for word in transcript.words:
    print(f"{word.start:.2f}s: {word.word}")
```

## 25.2 Text-to-Speech

```python
# OpenAI TTS
response = client.audio.speech.create(
    model="tts-1",
    voice="alloy",  # alloy, echo, fable, onyx, nova, shimmer
    input="Hello, how can I help you today?"
)

# Save to file
response.stream_to_file("output.mp3")

# Streaming for real-time
with client.audio.speech.with_streaming_response.create(
    model="tts-1",
    voice="alloy",
    input="This streams as it generates."
) as response:
    for chunk in response.iter_bytes():
        # Play or save chunk
        pass
```

## 25.3 Voice Assistant Pipeline

```python
class VoiceAssistant:
    def __init__(self):
        self.openai = OpenAI()
        self.anthropic = anthropic.Anthropic()

    async def process_audio(self, audio_path: str) -> str:
        # 1. Transcribe
        with open(audio_path, "rb") as f:
            transcript = self.openai.audio.transcriptions.create(
                model="whisper-1", file=f
            )

        # 2. Process with LLM
        response = await self.anthropic.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=500,
            messages=[{"role": "user", "content": transcript.text}]
        )
        answer = response.content[0].text

        # 3. Convert to speech
        audio = self.openai.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=answer
        )

        output_path = "response.mp3"
        audio.stream_to_file(output_path)
        return output_path
```

## 25.4 Local Speech Recognition

```python
import whisper

# Load model locally
model = whisper.load_model("base")  # tiny, base, small, medium, large

# Transcribe
result = model.transcribe("audio.mp3")
print(result["text"])

# With timestamps
for segment in result["segments"]:
    print(f"[{segment['start']:.1f}s] {segment['text']}")
```

## 25.5 Real-time Transcription

```python
import sounddevice as sd
import numpy as np
from queue import Queue

class RealtimeTranscriber:
    def __init__(self):
        self.model = whisper.load_model("base")
        self.audio_queue = Queue()
        self.sample_rate = 16000

    def audio_callback(self, indata, frames, time, status):
        self.audio_queue.put(indata.copy())

    def transcribe_stream(self):
        buffer = np.array([], dtype=np.float32)

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=self.audio_callback
        ):
            while True:
                # Collect audio chunks
                chunk = self.audio_queue.get()
                buffer = np.append(buffer, chunk.flatten())

                # Transcribe every 3 seconds
                if len(buffer) >= self.sample_rate * 3:
                    result = self.model.transcribe(buffer)
                    print(result["text"])
                    buffer = np.array([], dtype=np.float32)
```

## 25.6 Audio Processing

```python
from pydub import AudioSegment

def prepare_audio(input_path: str, output_path: str):
    """Prepare audio for transcription"""
    audio = AudioSegment.from_file(input_path)

    # Convert to mono
    audio = audio.set_channels(1)

    # Set sample rate
    audio = audio.set_frame_rate(16000)

    # Normalize volume
    audio = audio.normalize()

    audio.export(output_path, format="wav")

def split_long_audio(path: str, max_seconds: int = 60) -> list[str]:
    """Split long audio into chunks"""
    audio = AudioSegment.from_file(path)
    chunks = []

    for i, start in enumerate(range(0, len(audio), max_seconds * 1000)):
        chunk = audio[start:start + max_seconds * 1000]
        chunk_path = f"chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)

    return chunks
```

## 25.7 Voice Cloning Basics

```python
# Using ElevenLabs for voice cloning
from elevenlabs import clone, generate

# Clone from samples
voice = clone(
    name="My Voice",
    files=["sample1.mp3", "sample2.mp3", "sample3.mp3"],
)

# Generate with cloned voice
audio = generate(
    text="Hello, this is my cloned voice!",
    voice=voice
)

with open("cloned_output.mp3", "wb") as f:
    f.write(audio)
```

## 25.8 Summary

| Task | Tool |
|------|------|
| Transcription (cloud) | Whisper API |
| Transcription (local) | whisper.cpp, faster-whisper |
| TTS (cloud) | OpenAI TTS, ElevenLabs |
| TTS (local) | Coqui TTS, Piper |
| Voice cloning | ElevenLabs, Coqui |

**Best practices:**
- Preprocess audio for better accuracy
- Use appropriate model size for latency needs
- Handle long audio by chunking
- Consider privacy for voice data
- Test with various accents/noise levels
