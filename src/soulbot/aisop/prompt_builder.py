"""AisopPromptBuilder — convert AISOP/AISIP blueprints to LLM system prompts."""

from __future__ import annotations

import json

from .schema import AisopBlueprint


class AisopPromptBuilder:
    """Build LLM system prompts from AISOP/AISIP blueprints.

    The generated prompt includes:
    1. Optional base prompt
    2. Full blueprint as JSON (protocol-aware label)
    3. Optional workspace directory info
    4. Optional scheduling capability notice
    5. Blueprint system directive
    """

    def build(
        self,
        blueprint: AisopBlueprint,
        *,
        base_prompt: str = "",
        workspace_dir: str = "",
        enable_schedule: bool = False,
    ) -> str:
        """Build a system prompt from a blueprint.

        Args:
            blueprint: The AISOP blueprint to convert.
            base_prompt: Prepended base instructions.
            workspace_dir: Working directory path to include.
            enable_schedule: Whether to add scheduling instructions.

        Returns:
            Complete system prompt string.
        """
        parts: list[str] = []

        # 1. Base prompt
        if base_prompt:
            parts.append(base_prompt)

        # 2. Blueprint (full JSON, protocol-aware label)
        proto = blueprint.protocol.upper()
        ext = ".aisop.json" if blueprint.protocol == "aisop" else ".aisip.json"
        parts.append(f"[LOADED {proto}: {blueprint.name}{ext}]")
        parts.append("```json")
        parts.append(
            json.dumps(blueprint.model_dump(), ensure_ascii=False, indent=2)
        )
        parts.append("```")

        # 3. Workspace info
        if workspace_dir:
            parts.append(
                f"[WORKSPACE]\nYour AISOPs directory is: {workspace_dir}"
            )

        # 4. Schedule capability
        if enable_schedule:
            parts.append(
                "[SCHEDULE]\n"
                "You have scheduling capability. "
                "Use <!--SOULBOT_CMD:{...}--> to manage schedules."
            )

        # 5. System directive
        if blueprint.system_directive:
            parts.append(f"[DIRECTIVE]\n{blueprint.system_directive}")

        return "\n\n".join(parts)
