"""
Recipe loader for reporting recipes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from .models import ReportRecipe


class ReportRecipeLoader:
    def __init__(self, recipe_directory: str = "recipes"):
        self.recipe_directory = Path(recipe_directory)
        self._cache: Dict[str, ReportRecipe] = {}
        self.recipe_directory.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"ReportRecipeLoader initialized with directory: {self.recipe_directory}"
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

    def load_recipe(self, name: str) -> ReportRecipe:
        if name in self._cache:
            return self._cache[name]
        path = self._find_recipe_file(name)
        if not path:
            raise FileNotFoundError(f"Report recipe not found: {name}")
        recipe = ReportRecipe.from_yaml(str(path))
        recipe.validate()
        self._cache[name] = recipe
        logger.info(f"Loaded report recipe: {name}")
        return recipe
