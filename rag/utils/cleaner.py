import re


class TextCleaner:
    """
    Cleans extracted document text before chunking.
    """

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""

        # Normalize line endings
        text = text.replace("\r\n", "\n")
        text = text.replace("\r", "\n")

        # Replace tabs with spaces
        text = text.replace("\t", " ")

        # Remove non-printable control characters
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)

        # Remove trailing spaces
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

        # Replace multiple spaces with a single space
        text = re.sub(r"[ ]{2,}", " ", text)

        # Replace multiple blank lines with a single blank line
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove leading and trailing whitespace
        text = text.strip()

        return text