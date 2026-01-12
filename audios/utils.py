"""Audio utility functions for format conversion and validation"""

from fastapi import UploadFile, HTTPException
from pydub import AudioSegment
import os
import logging

logger = logging.getLogger(__name__)

# Allowed audio file extensions
ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.webm', '.ogg', '.m4a', '.flac'}

# MIME type mappings
ALLOWED_MIME_TYPES = {
    'audio/mpeg',
    'audio/mp3',
    'audio/wav',
    'audio/x-wav',
    'audio/wave',
    'audio/webm',
    'audio/ogg',
    'audio/x-m4a',
    'audio/flac'
}


def validate_audio_file(file: UploadFile, max_size: int = 10 * 1024 * 1024) -> None:
    filename=str(file.filename)
    file_ext = filename.lower().rsplit('.', 1)[-1]
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check MIME type if available
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning(f"Unexpected MIME type: {file.content_type} for {file.filename}")
    # Check file size
    content = file.file.read()
    file.file.seek(0)  # Reset file pointer for future reads
    file_size = len(content)

    if file_size > max_size:
        logger.error(f"File too large: {file_size} bytes > {max_size} bytes")
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {max_size / (1024 * 1024):.1f}MB"
        )
    



def convert_to_wav(input_path: str, output_path: str) -> str:
    try:
        logger.info(f"Converting {input_path} to WAV format")
        # Load audio file using pydub (supports many formats via ffmpeg)
        audio = AudioSegment.from_file(input_path)
        # Export as WAV
        audio.export(
            output_path,
            format='wav',
            parameters=[
                "-ac", "1",  # Mono
                "-ar", "16000"  # 16kHz sample rate (will be resampled by librosa anyway)
            ]
        )
        logger.info(f"Successfully converted to {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Failed to convert audio: {str(e)}")
        raise Exception(f"Audio conversion failed: {str(e)}")


def get_audio_duration(file_path: str) -> float:
    try:
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0  # Convert milliseconds to seconds
    except Exception as e:
        logger.warning(f"Could not get audio duration: {str(e)}")
        return 0.0


def is_audio_too_short(file_path: str, min_duration: float = 0.5) -> bool:
    duration = get_audio_duration(file_path)
    if duration > 0 and duration < min_duration:
        logger.warning(f"Audio too short: {duration:.2f}s < {min_duration}s")
        return True
    return False
