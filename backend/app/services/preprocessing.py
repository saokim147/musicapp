import os
import sys
import librosa
import numpy as np
import logging

from backend.app.config import settings
from audios import stft, tools
from audios.utils import convert_to_wav, is_audio_too_short
from backend.app.utils.file_manager import cleanup_file, create_temp_path
sys.path.insert(0, settings.PROJECT_ROOT)

logger = logging.getLogger(__name__)
class PreprocessingError(Exception):
    pass

class PreprocessingService:
    def __init__(self):
        self.stft = stft.TacotronSTFT(
            filter_length=settings.FILTER_LENGTH,    
            hop_length=settings.HOP_LENGTH,          
            win_length=settings.WIN_LENGTH,          
            n_mel_channels=settings.N_MEL_CHANNELS,  
            sampling_rate=settings.SAMPLING_RATE,    
            mel_fmin=settings.MEL_FMIN,              
            mel_fmax=settings.MEL_FMAX,              
        )
        self.sampling_rate = settings.SAMPLING_RATE
        self.max_wav_value = settings.MAX_WAV_VALUE
    def audio_to_melspec(self, audio: np.ndarray) -> np.ndarray:
        audio = audio.astype(np.float32)
        audio = audio / max(abs(audio)) * self.max_wav_value
        mel_spectrogram, _ = tools.get_mel_from_wav(audio, self.stft)
        mel_spectrogram = mel_spectrogram.T
        return mel_spectrogram
    def process_audio_file(self, file_path: str) -> np.ndarray:
        temp_wav_path = None
        try:
            # Check if audio is too short
            if is_audio_too_short(file_path, min_duration=0.5):
                raise PreprocessingError("Audio file is too short (< 0.5 seconds)")

            # Convert to WAV if needed
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in ['.wav']:
                logger.info(f"Converting {file_ext} to WAV")
                temp_wav_path = create_temp_path(settings.UPLOAD_DIR, prefix="converted_", suffix=".wav")
                convert_to_wav(file_path, temp_wav_path)
                audio_path = temp_wav_path
            else:
                audio_path = file_path

            # Load audio with librosa at target sampling rate
            logger.info(f"Loading audio from {audio_path}")
            audio, sr = librosa.load(audio_path, sr=self.sampling_rate)

            if len(audio) == 0:
                raise PreprocessingError("Audio file is empty or corrupted")
            # Convert to mel-spectrogram
            mel_spec = self.audio_to_melspec(audio)

            return mel_spec

        except Exception as e:
            raise PreprocessingError(f"Failed to process audio file: {str(e)}")

        finally:
            if temp_wav_path:
                cleanup_file(temp_wav_path)
    def preprocess_for_inference(self, file_path: str) -> tuple[np.ndarray, dict]:
        mel_spec = self.process_audio_file(file_path)

        metadata = {
            "original_shape": mel_spec.shape,
            "time_steps": mel_spec.shape[0],
            "mel_channels": mel_spec.shape[1]
        }

        return mel_spec, metadata