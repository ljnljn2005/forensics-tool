from typing import Any


def detect_file_signature(header: bytes) -> dict[str, Any]:
    if header.startswith(b"SQLite format 3\x00"):
        return {
            "kind": "database",
            "format": "sqlite",
            "mime": "application/vnd.sqlite3",
            "preferred_extension": ".db",
        }

    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return {
            "kind": "image",
            "format": "png",
            "mime": "image/png",
            "preferred_extension": ".png",
        }

    if header[:3] == b"\xff\xd8\xff":
        return {
            "kind": "image",
            "format": "jpeg",
            "mime": "image/jpeg",
            "preferred_extension": ".jpg",
        }

    if header.startswith((b"GIF87a", b"GIF89a")):
        return {
            "kind": "image",
            "format": "gif",
            "mime": "image/gif",
            "preferred_extension": ".gif",
        }

    if header.startswith(b"BM"):
        return {
            "kind": "image",
            "format": "bmp",
            "mime": "image/bmp",
            "preferred_extension": ".bmp",
        }

    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return {
            "kind": "image",
            "format": "webp",
            "mime": "image/webp",
            "preferred_extension": ".webp",
        }

    if len(header) >= 12 and header[4:8] == b"ftyp":
        major_brand = header[8:12]
        if major_brand in {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"MSNV", b"3gp4", b"3gp5", b"qt  ", b"M4V "}:
            return {
                "kind": "video",
                "format": "mp4",
                "mime": "video/mp4",
                "preferred_extension": ".mp4",
            }
        if major_brand in {b"M4A ", b"M4B ", b"M4P "}:
            return {
                "kind": "audio",
                "format": "m4a",
                "mime": "audio/mp4",
                "preferred_extension": ".m4a",
            }

    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"AVI ":
        return {
            "kind": "video",
            "format": "avi",
            "mime": "video/x-msvideo",
            "preferred_extension": ".avi",
        }

    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return {
            "kind": "video",
            "format": "mkv",
            "mime": "video/x-matroska",
            "preferred_extension": ".mkv",
        }

    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return {
            "kind": "audio",
            "format": "wav",
            "mime": "audio/wav",
            "preferred_extension": ".wav",
        }

    if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
        return {
            "kind": "audio",
            "format": "mp3",
            "mime": "audio/mpeg",
            "preferred_extension": ".mp3",
        }

    if header.startswith(b"OggS"):
        return {
            "kind": "audio",
            "format": "ogg",
            "mime": "audio/ogg",
            "preferred_extension": ".ogg",
        }

    if header.startswith(b"fLaC"):
        return {
            "kind": "audio",
            "format": "flac",
            "mime": "audio/flac",
            "preferred_extension": ".flac",
        }

    if len(header) >= 2 and header[0] == 0xFF and header[1] in {0xF1, 0xF9}:
        return {
            "kind": "audio",
            "format": "aac",
            "mime": "audio/aac",
            "preferred_extension": ".aac",
        }

    return {
        "kind": "unknown",
        "format": "",
        "mime": "application/octet-stream",
        "preferred_extension": "",
    }
