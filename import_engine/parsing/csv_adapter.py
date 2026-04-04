import csv
import io
from import_engine.parsing.base_adapter import BaseParserAdapter


class CSVAdapter(BaseParserAdapter):
    def __init__(self, file_path_or_buffer):
        super().__init__(file_path_or_buffer)
        if isinstance(self.source, str):
            self.file_obj = open(self.source, "r", encoding="utf-8-sig")
        else:

            try:

                preview = self.source.read(1)
                self.source.seek(0)
                if isinstance(preview, bytes):

                    self.file_obj = io.TextIOWrapper(
                        self.source, encoding="utf-8-sig", newline=""
                    )
                else:

                    self.file_obj = self.source
            except (AttributeError, io.UnsupportedOperation):

                self.file_obj = self.source

        self.reader = csv.DictReader(self.file_obj)

    def get_headers(self) -> list[str]:
        return self.reader.fieldnames or []

    def iter_rows(self, start_row: int = 1, end_row: int = None):
        for idx, row in enumerate(self.reader, start=1):
            if idx < start_row:
                continue
            if end_row and idx > end_row:
                break
            yield idx, row

    def chunked_read(self, chunk_size=1000):
        chunk = []
        for idx, row in enumerate(self.reader, start=1):
            chunk.append((idx, row))
            if len(chunk) == chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    def close(self):
        if isinstance(self.source, str) and not self.file_obj.closed:
            self.file_obj.close()
