import sys
import logging
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from core.voice.voice_worker import VoiceWorker
from core.voice.voice_job import VoiceJob
from core.voice.voice_config import VoiceConfig
from core.voice.voice_profile import VoiceProfile

logging.basicConfig(level=logging.INFO)

# Use the real F5-TTS bundled example audio so the engine has a valid ref file.
# The transcription below is the exact spoken text in basic_ref_en.wav.
_ORIGINAL_AUDIO = Path(__file__).parent / ".venv" / "Lib" / "site-packages" / "f5_tts" / "infer" / "examples" / "basic" / "basic_ref_en.wav"

# F5-TTS requires an 8-15 second reference audio. basic_ref_en.wav is only ~5s.
# We will loop it twice to make it ~10s and duplicate the text.
import soundfile as sf
import numpy as np

_REF_AUDIO = Path("temp/basic_ref_en_looped.wav")
_REF_AUDIO.parent.mkdir(exist_ok=True)
if _ORIGINAL_AUDIO.exists():
    data, sr = sf.read(str(_ORIGINAL_AUDIO))
    looped_data = np.concatenate([data, data])
    sf.write(str(_REF_AUDIO), looped_data, sr)

_REF_TEXT  = "Some call me nature, others call me mother nature. Some call me nature, others call me mother nature."

def run_test():
    if not _REF_AUDIO.exists():
        print(f"ERROR: Reference audio not found at: {_REF_AUDIO}")
        return

    profile = VoiceProfile(
        name="test",
        ref_audio_path=_REF_AUDIO,
        ref_text=_REF_TEXT,
    )
    config = VoiceConfig(
        script_text="Hello world.",
        output_audio_path=Path("temp/out.wav"),
        profile=profile,
    )
    job = VoiceJob(config)
    worker = VoiceWorker(job)
    worker.run()

    print("Final status:", job.status)
    if job.error_message:
        print("Error:", job.error_message)

if __name__ == "__main__":
    run_test()
