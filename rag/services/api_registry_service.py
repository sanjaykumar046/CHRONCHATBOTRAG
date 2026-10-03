import json
from pathlib import Path


class APIRegistryService:
    """
    Loads and provides access to the API Registry.

    Responsibilities
    ----------------
    - Load api_registry.json
    - Return all registry entries
    - Find a registry entry by intent

    Does NOT:
    - Call APIs
    - Perform RBAC
    - Validate parameters
    - Use the LLM
    """

    def __init__(self):

        project_root = Path(__file__).resolve().parents[2]

        self.registry_file = (
            project_root /
            "registry" /
            "api_registry_Correct.json"
        )

        self.registry = self._load()

    def _load(self):

        if not self.registry_file.exists():
            raise FileNotFoundError(
                f"Registry not found: {self.registry_file}"
            )

        with open(
            self.registry_file,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    def get_all(self):
        """
        Return all registry entries.
        """

        return self.registry

    def get_by_intent(self, intent_name):
        """
        Return a registry entry matching the given intent.
        """

        for item in self.registry:

            if (
                item.get("Intent Name", "").strip().lower()
                ==
                intent_name.strip().lower()
            ):
                return item

        return None

    def exists(self, intent_name):
        """
        Check whether an intent exists.
        """

        return self.get_by_intent(intent_name) is not None

