from pathlib import Path
from rag.config import KNOWLEDGE_BASE_PATH


class DocumentLoader:
    """
    Loads documents from the knowledge base.
    Currently supports TXT files.
    """

    SUPPORTED_EXTENSIONS = {".txt"}

    def load_documents(self):
        documents = []

        # Scan all files recursively
        for file_path in KNOWLEDGE_BASE_PATH.rglob("*"):

            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                continue

            document = self._load_txt(file_path)

            if document:
                documents.append(document)

        return documents

    def _load_txt(self, file_path: Path):

        try:
            content = file_path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            return {
                "module": file_path.parent.name,
                "page": file_path.stem,
                "source": str(file_path),
                "content": content
            }

        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return None