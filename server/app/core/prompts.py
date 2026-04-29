"""Prompt management system with YAML templates and versioning."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import yaml


class PromptTemplate:
    """A versioned prompt template loaded from YAML."""

    def __init__(self, name: str, system_prompt: str, user_prompt: str = "",
                 version: str = "1.0.0", description: str = "",
                 input_variables: list[str] | None = None) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.version = version
        self.description = description
        self.input_variables = input_variables or []
        self._checksum = self._compute_checksum()

    def render_system(self, **kwargs) -> str:
        """Render system prompt with variables."""
        return self.system_prompt.format(**kwargs) if kwargs else self.system_prompt

    def render_user(self, **kwargs) -> str:
        """Render user prompt with variables."""
        return self.user_prompt.format(**kwargs) if kwargs else self.user_prompt

    @property
    def checksum(self) -> str:
        return self._checksum

    def _compute_checksum(self) -> str:
        content = f"{self.system_prompt}{self.user_prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "checksum": self.checksum,
            "description": self.description,
            "input_variables": self.input_variables,
        }


class PromptManager:
    """Load and manage versioned prompt templates from YAML files."""

    def __init__(self, prompts_dir: str | Path = "") -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self._load_history: list[dict] = []
        if prompts_dir:
            self.load_from_dir(Path(prompts_dir))

    def load_from_dir(self, directory: Path) -> None:
        """Load all .yaml prompt files from a directory."""
        if not directory.exists():
            raise FileNotFoundError(f"Prompt directory not found: {directory}")

        for yaml_file in sorted(directory.glob("*.yaml")):
            self._load_file(yaml_file)

    def _load_file(self, filepath: Path) -> None:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "name" not in data:
            raise ValueError(f"Invalid prompt file: {filepath}")

        template = PromptTemplate(
            name=data["name"],
            system_prompt=data.get("system_prompt", ""),
            user_prompt=data.get("user_prompt", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            input_variables=data.get("input_variables", []),
        )

        self._templates[template.name] = template
        self._load_history.append({
            "name": template.name,
            "version": template.version,
            "checksum": template.checksum,
            "file": str(filepath),
            "loaded_at": datetime.now(timezone.utc).isoformat(),
        })

    def get(self, name: str) -> PromptTemplate:
        if name not in self._templates:
            available = list(self._templates.keys())
            raise KeyError(f"Prompt '{name}' not found. Available: {available}")
        return self._templates[name]

    def list_all(self) -> list[dict]:
        return [t.to_dict() for t in self._templates.values()]

    def list_versions(self) -> dict[str, str]:
        return {t.name: t.version for t in self._templates.values()}

    def get_load_history(self) -> list[dict]:
        return self._load_history

    @property
    def template_count(self) -> int:
        return len(self._templates)


# Global prompt manager - initialized at app startup
prompt_manager = PromptManager()
