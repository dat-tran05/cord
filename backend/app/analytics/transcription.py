import logging

from deepgram import DeepgramClient, PrerecordedOptions

from app.config import settings

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/wav") -> dict:
    """Transcribe audio using Deepgram. Returns transcript with speaker diarization."""
    if not settings.deepgram_api_key:
        logger.warning("Deepgram API key not set, skipping transcription")
        return {"transcript": "", "words": []}

    client = DeepgramClient(settings.deepgram_api_key)
    options = PrerecordedOptions(
        model="nova-2",
        smart_format=True,
        diarize=True,
    )
    source = {"buffer": audio_bytes, "mimetype": mimetype}
    response = await client.listen.asyncrest.v("1").transcribe_file(source, options)
    result = response.to_dict()

    return {
        "transcript": result.get("results", {}).get("channels", [{}])[0]
            .get("alternatives", [{}])[0].get("transcript", ""),
        "words": result.get("results", {}).get("channels", [{}])[0]
            .get("alternatives", [{}])[0].get("words", []),
    }
