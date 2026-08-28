"""Background worker thread executing audio preprocessing, F5-TTS voice cloning inference,
and long script audio segment merging.
"""

import logging
from pathlib import Path
import re
import sys
import threading
import traceback
from typing import Callable, List, Optional

import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as F

from core.voice.voice_config import VoiceConfig
from core.voice.voice_job import VoiceJob


class VoiceWorker(threading.Thread):
    """Executes audio preprocessing, downloads weights, runs F5-TTS, and compiles long speech clips."""

    def __init__(self, job: VoiceJob, on_complete_callback: Optional[Callable[[VoiceJob], None]] = None) -> None:
        """Initialize VoiceWorker.

        Args:
            job: VoiceJob instance.
            on_complete_callback: Callback triggered when job completes.
        """
        super().__init__(daemon=True)
        self.job = job
        self.on_complete = on_complete_callback
        self._logger = logging.getLogger(f"{self.__class__.__name__}_{job.job_id[:8]}")
        self._cancelled = False

    def run(self) -> None:
        """Execute the voice synthesis pipeline."""
        self._logger.info(f"Starting voice synthesis background worker for job {self.job.job_id}")
        self.job.update_status("running", 0.0)

        try:
            # 1. Resolve compute device (CUDA fallback to CPU)
            device = "cuda" if self.job.config.device == "cuda" and torch.cuda.is_available() else "cpu"
            self._logger.info(f"Selected execution compute device: {device}")

            # 2. Preprocess Reference Audio
            self.job.update_status("running", 0.1)
            ref_path = self.job.config.profile.ref_audio_path
            
            # Temporary path for preprocessed audio
            temp_dir = ref_path.parent / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            preprocessed_ref_path = temp_dir / f"preprocessed_{ref_path.name}"

            self._logger.info(f"Preprocessing reference audio {ref_path.name}...")
            self._preprocess_audio(ref_path, preprocessed_ref_path)

            # 3. Import F5-TTS and initialise the high-level API class
            # We import dynamically to avoid loading torch/CUDA on main window boot
            self.job.update_status("downloading_weights", 0.2)
            self._logger.info("Loading F5-TTS model layers (Downloading weights if missing)...")

            try:
                from f5_tts.api import F5TTS
            except ImportError as e:
                # If f5-tts is not installed/compiling correctly, we raise explaining requirements
                raise ImportError(
                    "F5-TTS library is not installed or import failed. Please verify that pip install completed successfully."
                ) from e

            # F5TTS() loads the named preset config, resolves the DiT model class,
            # downloads HF checkpoint weights if absent, and initialises the vocoder.
            # This is the correct high-level entry-point for this version of f5-tts.
            f5tts = F5TTS(
                model="F5TTS_v1_Base",
                ckpt_file="",        # empty → downloads from HuggingFace hub
                vocab_file="",
                device=device
            )
            sample_rate = f5tts.target_sample_rate  # resolved from model config (24000 Hz)

            # 4. Split long script text into punctuation-aware chunks
            self.job.update_status("running", 0.4)
            script_text = self.job.config.script_text
            chunks = self._split_script_into_chunks(script_text, max_chars=180)
            self._logger.info(f"Script split into {len(chunks)} text chunks for generation.")

            waveforms: List[torch.Tensor] = []

            # 5. Sequentially run F5-TTS on each text segment
            import torchaudio
            def _patched_torchaudio_load(filepath, **kwargs):
                return self._load_audio(Path(filepath))
            torchaudio.load = _patched_torchaudio_load

            for idx, chunk in enumerate(chunks):
                if self._cancelled:
                    raise RuntimeError("Job cancelled by user.")

                self._logger.info(f"Generating segment {idx + 1}/{len(chunks)}: '{chunk[:35]}...'")

                # Slices progress range from 0.4 to 0.95
                current_progress = 0.4 + (idx / len(chunks)) * 0.55
                self.job.update_status("running", current_progress)

                # Read duration of preprocessed ref audio
                import soundfile as sf
                ref_info = sf.info(str(preprocessed_ref_path))
                ref_dur = ref_info.frames / ref_info.samplerate

                self._logger.info("--- DEBUG INFO ---")
                self._logger.info(f"ref_file: {preprocessed_ref_path}")
                self._logger.info(f"ref_text: {self.job.config.profile.ref_text}")
                self._logger.info(f"gen_text: {chunk}")
                self._logger.info(f"Reference audio duration: {ref_dur:.2f}s")
                self._logger.info(f"Number of script chunks: {len(chunks)}")
                self._logger.info(f"Text of all chunks: {chunks}")
                self._logger.info("------------------")

                # Execute F5-TTS inference via the high-level API
                # Returns: (wav: np.ndarray [N], sample_rate: int, spectrogram)
                wav, sr, _ = f5tts.infer(
                    ref_file=str(preprocessed_ref_path),
                    ref_text=self.job.config.profile.ref_text,
                    gen_text=chunk,
                )

                # Convert numpy array to torch tensor [1, N]
                chunk_tensor = torch.from_numpy(wav).unsqueeze(0)
                waveforms.append(chunk_tensor)

            # 6. Merge segment waveforms together seamlessly
            self.job.update_status("running", 0.95)
            self._logger.info("Merging audio segments seamlessly...")

            if not waveforms:
                raise ValueError("No audio waveforms were generated from the script chunks.")

            # Concat audio clips along time dimension
            merged_waveform = torch.cat(waveforms, dim=-1)

            # Normalise merged output to avoid clipping
            max_val = torch.max(torch.abs(merged_waveform))
            if max_val > 0:
                merged_waveform = merged_waveform / max_val

            # Write final compiled audio WAV file
            self.job.config.output_audio_path.parent.mkdir(parents=True, exist_ok=True)
            # Convert [C, N] tensor → [N, C] numpy array for soundfile
            audio_np = merged_waveform.numpy().T
            sf.write(str(self.job.config.output_audio_path), audio_np, sample_rate, subtype="PCM_16")

            # Clean temporary preprocessed folder
            try:
                preprocessed_ref_path.unlink()
                if not any(temp_dir.iterdir()):
                    temp_dir.rmdir()
            except Exception:
                pass

            self.job.update_status("completed", 1.0)
            self._logger.info(f"Speech audio compiled and exported to: {self.job.config.output_audio_path}")

        except Exception as e:
            self._logger.error(f"Error executing speech synthesis job: {e}")
            tb = traceback.format_exc()
            self.job.update_status("failed", self.job.progress, error_message=tb)

        finally:
            if self.on_complete:
                try:
                    self.on_complete(self.job)
                except Exception as e:
                    self._logger.error(f"Error in on_complete callback: {e}")

    def _load_audio(self, path: Path) -> tuple:
        """Load an audio file to a float32 torch.Tensor without relying on TorchCodec.

        Tries backends in order:
          1. soundfile  — pure-Python, no FFmpeg dependency, handles WAV/FLAC/OGG
          2. librosa    — handles MP3 and other formats via its own backend

        Args:
            path: Audio file path (WAV, MP3, FLAC, …).

        Returns:
            Tuple of (waveform: torch.Tensor [C, N], sample_rate: int).
        """
        errors = []

        # ── 1. soundfile ─────────────────────────────────────────────────────
        try:
            data, sr = sf.read(str(path), dtype="float32", always_2d=True)
            # soundfile returns [N, C]; transpose to [C, N]
            waveform = torch.from_numpy(data.T.copy())
            self._logger.debug(f"Loaded audio via soundfile: {path.name} ({waveform.shape}, {sr} Hz)")
            return waveform, int(sr)
        except Exception as e:
            errors.append(f"soundfile: {e}")

        # ── 2. librosa ───────────────────────────────────────────────────────
        try:
            import librosa
            data, sr = librosa.load(str(path), sr=None, mono=False)
            # librosa returns [N] for mono or [C, N] for multi-channel
            if data.ndim == 1:
                data = data[np.newaxis, :]   # → [1, N]
            waveform = torch.from_numpy(data.astype(np.float32))
            self._logger.debug(f"Loaded audio via librosa: {path.name} ({waveform.shape}, {sr} Hz)")
            return waveform, int(sr)
        except Exception as e:
            errors.append(f"librosa: {e}")

        raise RuntimeError(
            f"Failed to load audio file '{path.name}' with soundfile and librosa backends.\n"
            + "\n".join(errors)
        )

    def _preprocess_audio(self, src: Path, dest: Path) -> None:
        """Load reference audio, convert to mono, normalize volume, resample to 24kHz, and trim silences.

        Args:
            src: Raw input WAV/MP3 path.
            dest: Target preprocessed WAV path.
        """
        # Load audio using TorchCodec-free backend chain
        waveform, sample_rate = self._load_audio(src)

        # Ensure float32 tensor
        if waveform.dtype != torch.float32:
            waveform = waveform.float()

        # Convert stereo to mono by averaging channels
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        # Resample to 24,000 Hz
        if sample_rate != 24000:
            waveform = F.resample(waveform, sample_rate, 24000)

        # Normalise amplitude peak
        max_val = torch.max(torch.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val

        # Trim Silence start/end using an energy gate threshold
        # Compute local window energy to avoid trimming internal speech pauses
        win_len = 1024
        energy = torch.sqrt(torch.mean(waveform.unfold(1, win_len, win_len) ** 2, dim=-1))

        # Gate threshold (amplitude limit)
        threshold = 0.012
        active_blocks = (energy > threshold).nonzero()

        if len(active_blocks) > 0:
            start_idx = int(active_blocks[0][1]) * win_len
            end_idx = min(int(active_blocks[-1][1] + 1) * win_len, waveform.shape[1])

            # Crop waveform
            waveform = waveform[:, start_idx:end_idx]

        # Normalise cropped output
        max_val = torch.max(torch.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val

        # Save to preprocessed path (soundfile expects [N, C] numpy array)
        audio_np = waveform.numpy().T
        sf.write(str(dest), audio_np, 24000, subtype="PCM_16")


    def _split_script_into_chunks(self, text: str, max_chars: int = 180) -> List[str]:
        """Split script text at punctuation limits to create short segments for F5-TTS.

        Args:
            text: Script text to split.
            max_chars: Target character limit for each segment.

        Returns:
            List of sentence segments.
        """
        # Clean spacing
        text = " ".join(text.split())
        
        # Split by punctuation sentence boundaries (. ! ?) keeping the punctuation marks
        sentence_ends = re.compile(r"(?<=[.!?])\s+")
        sentences = sentence_ends.split(text)

        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If a single sentence exceeds the max limit, we split it by commas or spaces
            if len(sentence) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                # Split long sentence by commas or spaces
                sub_clauses = re.split(r"(?<=,)\s+", sentence)
                for clause in sub_clauses:
                    if len(clause) > max_chars:
                        # Split by space
                        words = clause.split()
                        sub_chunk = ""
                        for word in words:
                            if len(sub_chunk) + len(word) + 1 > max_chars:
                                chunks.append(sub_chunk)
                                sub_chunk = word
                            else:
                                sub_chunk = f"{sub_chunk} {word}" if sub_chunk else word
                        if sub_chunk:
                            current_chunk = sub_chunk
                    else:
                        if len(current_chunk) + len(clause) + 1 > max_chars:
                            chunks.append(current_chunk)
                            current_chunk = clause
                        else:
                            current_chunk = f"{current_chunk} {clause}" if current_chunk else clause
            else:
                if len(current_chunk) + len(sentence) + 1 > max_chars:
                    chunks.append(current_chunk)
                    current_chunk = sentence
                else:
                    current_chunk = f"{current_chunk} {sentence}" if current_chunk else sentence

        if current_chunk:
            chunks.append(current_chunk)

        # Sanitize segments to ensure F5-TTS compatibility (e.g. clean multiple spaces)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def cancel(self) -> None:
        """Cancel execution."""
        self._cancelled = True
