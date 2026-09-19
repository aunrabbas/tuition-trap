"""Atomic JSON response cache with credential-free request fingerprints."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile


class CacheError(RuntimeError):
    """Cached data cannot be read or written safely."""


class CacheMissError(CacheError):
    """An offline request has no saved response."""


class JSONCache:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def path_for(self, params: dict) -> Path:
        if any("key" in key.lower() and key != "keys_nested" for key in params):
            raise CacheError("Credentials must not be included in cache parameters.")
        encoded = json.dumps(params, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
        return self.directory / f"scorecard-{fingerprint}.json"

    def read(self, params: dict) -> dict | None:
        path = self.path_for(params)
        if not path.exists():
            return None
        try:
            document = json.loads(path.read_text())
            if document["schema_version"] != 1 or document["request"] != params:
                raise ValueError
            if not isinstance(document["response"], dict):
                raise ValueError
            return document["response"]
        except (OSError, ValueError, KeyError, TypeError):
            raise CacheError("Scorecard cache is invalid; restore the committed seed files.") from None

    def write(self, params: dict, response: dict) -> None:
        path = self.path_for(params)
        document = {
            "schema_version": 1,
            "source": "U.S. Department of Education College Scorecard API",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "request": params,
            "response": response,
        }
        temporary = None
        try:
            encoded = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded)
            temporary.replace(path)
        except (OSError, ValueError, TypeError):
            raise CacheError("Could not save the Scorecard response; check seed directory permissions.") from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
