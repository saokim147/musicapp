from fastapi import UploadFile
from contextlib import contextmanager
import uuid
import os
import logging
import shutil

logger = logging.getLogger(__name__)

def save_upload_file(upload_file: UploadFile, upload_dir: str) -> str:
    os.makedirs(upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    filename=str(upload_file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    filename = f"{file_id}{file_ext}"
    file_path = os.path.join(upload_dir, filename)
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        logger.info(f"Saved upload file to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Failed to save upload file: {str(e)}")
        raise
    finally:
        upload_file.file.close()


def cleanup_file(file_path: str) -> None:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Cleaned up file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup file {file_path}: {str(e)}")


def cleanup_files(file_paths: list) -> None:
    for path in file_paths:
        cleanup_file(path)


@contextmanager
def temp_file_context(upload_file: UploadFile, upload_dir: str):
    temp_path = None
    try:
        temp_path = save_upload_file(upload_file, upload_dir)
        yield temp_path
    finally:
        if temp_path:
            cleanup_file(temp_path)

@contextmanager
def multi_temp_files_context(*file_paths):

    try:
        yield file_paths
    finally:
        cleanup_files(file_paths) # type: ignore


def create_temp_path(base_dir: str, prefix: str = "", suffix: str = "") -> str:
    os.makedirs(base_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    filename = f"{prefix}{file_id}{suffix}"
    return os.path.join(base_dir, filename)
