from abc import ABC, abstractmethod

class BaseParserAdapter(ABC):
    def __init__(self, file_path_or_buffer):
        self.source = file_path_or_buffer
        
    @abstractmethod
    def get_headers(self) -> list[str]:
        pass

    @abstractmethod
    def iter_rows(self, start_row: int = 1, end_row: int = None):
        """
        Yields (row_index, dict_of_row_data)
        """
        pass
        
    @abstractmethod
    def chunked_read(self, chunk_size=1000):
        pass

    def close(self):
        pass
