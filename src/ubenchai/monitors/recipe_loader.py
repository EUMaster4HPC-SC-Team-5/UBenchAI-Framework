"""
Recipe loader for monitor recipes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from .models import MonitorRecipe


class MonitorRecipeLoader:
    def __init__(self, recipe_directory: str = "recipes"):
        self.recipe_directory = Path(recipe_directory)
        self._cache: Dict[str, MonitorRecipe] = {}
        self.recipe_directory.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"MonitorRecipeLoader initialized with directory: {self.recipe_directory}"
        )

    def _find_recipe_file(self, name: str) -> Optional[Path]:
        for ext in [".yml", ".yaml"]:
            candidate = self.recipe_directory / f"{name}{ext}"
            if candidate.exists():
                return candidate
        return None

    def list_available_recipes(self) -> List[str]:
        names: List[str] = []
        for pattern in ["*.yml", "*.yaml"]:
            for p in self.recipe_directory.glob(pattern):
                names.append(p.stem)
        return sorted(names)

    def load_recipe(self, name: str) -> MonitorRecipe:
        if name in self._cache:
            return self._cache[name]
        path = self._find_recipe_file(name)
        if not path:
            raise FileNotFoundError(f"Monitor recipe not found: {name}")
        recipe = MonitorRecipe.from_yaml(str(path))
        recipe.validate()
        self._cache[name] = recipe
        logger.info(f"Loaded monitor recipe: {name}")
        return recipe
