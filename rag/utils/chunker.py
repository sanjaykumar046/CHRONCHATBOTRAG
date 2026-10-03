from rag.config import CHUNK_SIZE, CHUNK_OVERLAP


class TextChunker:
    """
    Generic text chunker.

    Splits text into overlapping chunks based on
    configurable chunk size and overlap.
    """

    @staticmethod
    def chunk(document: dict) -> list:
        """
        Parameters
        ----------
        document : dict
            {
                "module": "...",
                "page": "...",
                "source": "...",
                "content": "..."
            }

        Returns
        -------
        list
            List of chunk dictionaries.
        """

        text = document["content"]

        chunks = []

        start = 0
        chunk_number = 1

        while start < len(text):

            end = start + CHUNK_SIZE

            chunk_text = text[start:end].strip()

            if chunk_text:

                chunks.append({
                    "chunk_id": chunk_number,
                    "module": document["module"],
                    "page": document["page"],
                    "source": document["source"],
                    "content": chunk_text
                })

            chunk_number += 1

            start += (CHUNK_SIZE - CHUNK_OVERLAP)

        return chunks