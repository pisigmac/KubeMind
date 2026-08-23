"""Real-time streaming token de-anonymization transformer.

Enables Server-Sent Events (SSE) streaming while de-anonymizing pseudonymized
entity tokens (e.g. `[KM_PERSON_1]`, `[KM_ADDRESS_1]`) on-the-fly across
arbitrary chunk boundaries without leaking tokens or introducing latency.
"""

from typing import Dict, List, Set


class StreamingDeAnonymizer:
    """Stream transformer that buffers potential token prefixes and swaps real values."""

    def __init__(self, token_map: Dict[str, str] | None = None):
        self.token_map = token_map or {}
        self.buffer = ""
        self.token_prefixes: Set[str] = set()
        self.max_token_len = 0

        for token in self.token_map.keys():
            self.max_token_len = max(self.max_token_len, len(token))
            for i in range(1, len(token) + 1):
                self.token_prefixes.add(token[:i])

    def transform_chunk(self, chunk: str) -> str:
        """Process an incoming delta chunk and return text ready to emit."""
        if not self.token_map:
            return chunk

        self.buffer += chunk
        output: List[str] = []

        while self.buffer:
            # Check if there is an opening bracket '[' in the buffer
            bracket_idx = self.buffer.find("[")
            if bracket_idx == -1:
                # No bracket at all in buffer, safely emit everything
                output.append(self.buffer)
                self.buffer = ""
                break

            if bracket_idx > 0:
                # Emit everything before the bracket
                output.append(self.buffer[:bracket_idx])
                self.buffer = self.buffer[bracket_idx:]

            # Now self.buffer starts with '['
            # Check if the entire buffer or a prefix of it matches a known token
            matched_exact = False
            for token, real_val in self.token_map.items():
                if self.buffer.startswith(token):
                    output.append(real_val)
                    self.buffer = self.buffer[len(token):]
                    matched_exact = True
                    break

            if matched_exact:
                continue

            # Check if self.buffer is a valid prefix of ANY token
            if self.buffer in self.token_prefixes:
                # Buffer could be the start of a token, wait for more chunks (unless exceeded max token len)
                if len(self.buffer) >= self.max_token_len:
                    # Exceeded max token length and not matched, flush first char and loop
                    output.append(self.buffer[0])
                    self.buffer = self.buffer[1:]
                else:
                    break
            else:
                # Buffer starts with '[' but is NOT a prefix of any token (e.g. '[123]' or '[foo]')
                output.append(self.buffer[0])
                self.buffer = self.buffer[1:]

        return "".join(output)

    def flush(self) -> str:
        """Flush any remaining buffered characters at stream end."""
        remaining = self.buffer
        self.buffer = ""
        # Final replacement check on remaining buffer
        for token, real_val in self.token_map.items():
            remaining = remaining.replace(token, real_val)
        return remaining
