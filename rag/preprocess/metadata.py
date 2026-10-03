"""
Metadata Generator

Creates metadata for each chunk before storing it in ChromaDB.
"""


class MetadataGenerator:

    @staticmethod
    def generate(document, chunk_id):

        return {
            "module": document["module"],
            "page": document["page"],
            "source": document["source"],
            "chunk_id": chunk_id
        }