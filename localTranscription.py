import whisperx
import gc
import torch
import os
import warnings
import sys
import ctypes
import logging
from typing import Optional

# Suppress ALL warnings for cleaner output
warnings.filterwarnings("ignore")
logging.getLogger("pytorch_lightning").setLevel(logging.ERROR)
logging.getLogger("whisperx").setLevel(logging.ERROR)

# Additional specific warning suppressions
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*pyannote.audio.*")
warnings.filterwarnings("ignore", message=".*torch.*")
warnings.filterwarnings("ignore", message=".*Model was trained with.*")

# Force GPU optimization settings - MANUAL DLL LOADING
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"
os.environ["CUDA_LAUNCH_BLOCKING"] = "0"
# Suppress compatibility warnings
os.environ["PYANNOTE_CACHE_DISABLE_WARNING"] = "1"
os.environ["PYTORCH_LIGHTNING_IGNORE_VERSION"] = "1"

# Set cuDNN PATH manually and load DLLs
cudnn_path = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cudnn", "bin")
if os.path.exists(cudnn_path):
    os.environ["PATH"] = cudnn_path + ";" + os.environ.get("PATH", "")

    # Try to manually load ALL cuDNN DLLs
    try:
        cudnn_dlls = [
            "cudnn_ops_infer64_8.dll",
            "cudnn_cnn_infer64_8.dll",
            "cudnn_ops_train64_8.dll",
            "cudnn_cnn_train64_8.dll",
            "cudnn_adv_infer64_8.dll",
            "cudnn_adv_train64_8.dll",
        ]

        for dll_name in cudnn_dlls:
            dll_path = os.path.join(cudnn_path, dll_name)
            if os.path.exists(dll_path):
                try:
                    ctypes.CDLL(dll_path)
                except Exception:
                    pass  # Silent fail for cleaner output
    except Exception:
        pass  # Silent fail for cleaner output

# Enable cuDNN and GPU optimizations
torch.backends.cudnn.enabled = True
torch.backends.cudnn.benchmark = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cuda.matmul.allow_tf32 = True

if torch.cuda.is_available():
    torch.cuda.empty_cache()
    torch.cuda.set_per_process_memory_fraction(0.95)


def transcribe_audio(mp3_path: str) -> str:
    """
    Transcribe an audio file to text using WhisperX with GPU acceleration.

    Args:
        mp3_path (str): Path to the audio file (MP3, WAV, M4A, FLAC, OGG)

    Returns:
        str: Complete transcript as a single string

    Raises:
        FileNotFoundError: If audio file doesn't exist
        Exception: For transcription errors
    """

    # Validate input
    if not os.path.exists(mp3_path):
        raise FileNotFoundError(f"Audio file not found: {mp3_path}")

    # Determine device and settings
    if torch.cuda.is_available():
        device = "cuda"
        compute_type = "float16"
        model_size = "large-v2"  # Best quality
        batch_size = 16
    else:
        device = "cpu"
        compute_type = "int8"
        model_size = "base"
        batch_size = 1

    try:
        # Use contextlib for safer output suppression (thread-safe)
        import contextlib
        from io import StringIO

        # Create string buffers to capture output safely
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()

        # Suppress all output during model loading and transcription
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(
            stderr_buffer
        ):
            # Load model
            model = whisperx.load_model(model_size, device, compute_type=compute_type)

            # Load audio
            audio = whisperx.load_audio(mp3_path)

            # Transcribe
            result = model.transcribe(audio, batch_size=batch_size, language="en")

        # Clean up model
        del model
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()

        # Perform alignment for better accuracy
        if result.get("segments"):
            try:
                # Create new buffers for alignment (safer than reusing)
                align_stdout = StringIO()
                align_stderr = StringIO()

                with contextlib.redirect_stdout(
                    align_stdout
                ), contextlib.redirect_stderr(align_stderr):
                    model_a, metadata = whisperx.load_align_model(
                        language_code=result["language"], device=device
                    )

                    result = whisperx.align(
                        result["segments"],
                        model_a,
                        metadata,
                        audio,
                        device,
                        return_char_alignments=False,
                    )

                del model_a
                gc.collect()
                if device == "cuda":
                    torch.cuda.empty_cache()
            except Exception:
                pass  # Continue with basic transcription if alignment fails

        # Extract transcript
        if result.get("segments"):
            transcript = " ".join(
                segment.get("text", "").strip()
                for segment in result["segments"]
                if segment.get("text", "").strip()
            )
        else:
            transcript = ""  # Return empty string instead of "No speech detected"

        # Final cleanup
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()

        return transcript

    except Exception as e:
        # Cleanup on error
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()
        raise Exception(f"Transcription failed: {str(e)}")


# Example usage
if __name__ == "__main__":
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
    else:
        # Default test file
        audio_file = r"C:/Proscan/Recordings/08-22-25/Middlesex/Middlesex; Municipalities - Newton; Fire Department - Dispatch; NFM; 482.962500; ID; #50.mp3"

    print("🎵 Starting transcription...")
    print("ℹ️  Note: Version compatibility warnings are normal and harmless")

    try:
        transcript = transcribe_audio(audio_file)
        print("\n" + "=" * 50)
        print("✅ TRANSCRIPTION COMPLETE")
        print("=" * 50)
        print(transcript)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
