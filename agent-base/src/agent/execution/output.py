from typing import IO


class OutputBuffer:
    def __init__(self, max_bytes: int = 64 * 1024):
        if max_bytes <= 0:
            raise ValueError("输出容器必须大于 0")

        self._max_bytes = max_bytes
        self._data = bytearray()
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        remaining = self._max_bytes - len(self._data)

        self._data.extend(chunk[:remaining])

        if len(chunk) > remaining:
            self.truncated = True

    @property
    def text(self) -> str:
        return self._data.decode("utf-8", errors="replace")        


def read_stream(
    stream: IO[bytes],
    output: OutputBuffer,        
) -> None:
    while True:
        chunk = stream.read(4096)

        if not chunk:
            break

        output.append(chunk)
    

        
