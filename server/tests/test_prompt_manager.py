import tempfile
from pathlib import Path

import pytest

from app.core.prompts import PromptManager, PromptTemplate


class TestPromptTemplate:
    def test_checksum_stability(self):
        t1 = PromptTemplate("test", "Hello {name}", version="1.0.0")
        t2 = PromptTemplate("test", "Hello {name}", version="1.0.0")
        assert t1.checksum == t2.checksum

    def test_checksum_changes_on_content_change(self):
        t1 = PromptTemplate("test", "Hello {name}")
        t2 = PromptTemplate("test", "Hello {name}!")
        assert t1.checksum != t2.checksum

    def test_render_system(self):
        t = PromptTemplate("test", "Hello {name}, welcome to {city}")
        result = t.render_system(name="Alice", city="Beijing")
        assert result == "Hello Alice, welcome to Beijing"

    def test_render_user(self):
        t = PromptTemplate("test", system_prompt="System", user_prompt="User: {query}")
        result = t.render_user(query="plan a trip")
        assert result == "User: plan a trip"

    def test_render_no_variables(self):
        t = PromptTemplate("test", "Static prompt")
        assert t.render_system() == "Static prompt"

    def test_to_dict(self):
        t = PromptTemplate("test", "Hello", version="2.0.0",
                           description="A test prompt", input_variables=["name"])
        d = t.to_dict()
        assert d["name"] == "test"
        assert d["version"] == "2.0.0"
        assert "checksum" in d


class TestPromptManager:
    def test_load_from_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test YAML prompt file
            prompt_yaml = Path(tmpdir) / "test_agent.yaml"
            prompt_yaml.write_text("""
name: test_agent
version: "1.2.0"
description: A test prompt
system_prompt: "You are a test agent. Answer: {query}"
input_variables:
  - query
""", encoding="utf-8")

            pm = PromptManager(str(tmpdir))
            assert pm.template_count == 1
            t = pm.get("test_agent")
            assert t.version == "1.2.0"
            assert t.description == "A test prompt"
            assert "query" in t.input_variables

    def test_load_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "agent_a.yaml").write_text("""
name: agent_a
version: "1.0.0"
system_prompt: "Agent A prompt"
""", encoding="utf-8")
            (Path(tmpdir) / "agent_b.yaml").write_text("""
name: agent_b
version: "2.0.0"
system_prompt: "Agent B prompt"
""", encoding="utf-8")

            pm = PromptManager(str(tmpdir))
            assert pm.template_count == 2

    def test_get_missing_raises(self):
        pm = PromptManager()
        with pytest.raises(KeyError, match="nonexistent"):
            pm.get("nonexistent")

    def test_list_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "agent.yaml").write_text("""
name: agent
version: "1.0.0"
system_prompt: "Prompt"
""", encoding="utf-8")

            pm = PromptManager(str(tmpdir))
            all_prompts = pm.list_all()
            assert len(all_prompts) == 1
            assert all_prompts[0]["name"] == "agent"

    def test_list_versions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.yaml").write_text("""
name: a
version: "1.5.0"
system_prompt: "A"
""", encoding="utf-8")

            pm = PromptManager(str(tmpdir))
            versions = pm.list_versions()
            assert versions["a"] == "1.5.0"

    def test_load_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "x.yaml").write_text("""
name: x
version: "1.0.0"
system_prompt: "X"
""", encoding="utf-8")

            pm = PromptManager(str(tmpdir))
            history = pm.get_load_history()
            assert len(history) == 1
            assert history[0]["name"] == "x"
            assert history[0]["version"] == "1.0.0"

    def test_directory_not_found(self):
        with pytest.raises(FileNotFoundError):
            PromptManager("/nonexistent/directory")

    def test_load_prompts_from_agents_dir(self):
        """Integration test: load actual agent prompts."""
        import os
        prompts_dir = Path(__file__).parent.parent / "app" / "agents" / "prompts"
        if prompts_dir.exists():
            pm = PromptManager(str(prompts_dir))
            assert pm.template_count >= 5  # At least 5 agents
            # Verify key agents exist
            pm.get("IntentAgent")
            pm.get("MemoryAgent")
            pm.get("WeatherAgent")
            pm.get("BudgetAgent")
            pm.get("CriticAgent")
