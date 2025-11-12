"""
MonitorRecipeLoader - Manages discovery, loading, and validation of monitor recipes
"""

from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger

from ubenchai.monitors.recipes import MonitorRecipe


class MonitorRecipeLoader:
    """Manages discovery, validation, and loading of monitor recipes"""

    def __init__(self, recipe_directory: str = "recipes/monitors"):
        """Initialize MonitorRecipeLoader"""
        self.recipe_directory = Path(recipe_directory)
        self._cache: Dict[str, MonitorRecipe] = {}

        self.recipe_directory.mkdir(parents=True, exist_ok=True)

        logger.info(f"MonitorRecipeLoader initialized: {self.recipe_directory}")

    def load_recipe(self, name: str) -> MonitorRecipe:
        """Load a monitor recipe by name"""
        # Check cache
        if name in self._cache:
            logger.debug(f"Loading recipe from cache: {name}")
            return self._cache[name]

        # Find recipe file
        recipe_path = self._find_recipe_file(name)
        if not recipe_path:
            raise FileNotFoundError(f"Recipe not found: {name}")

        # Load and validate
        recipe = MonitorRecipe.from_yaml(str(recipe_path))

        # Validate
        errors = self.validate_recipe(recipe)
        if errors:
            error_msg = f"Recipe validation failed: {', '.join(errors)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Cache it
        self._cache[name] = recipe
        logger.info(f"Loaded and cached recipe: {name}")

        return recipe

    def validate_recipe(self, recipe: MonitorRecipe) -> List[str]:
        """Validate a recipe"""
        errors = []

        try:
            recipe.validate()
        except ValueError as e:
            errors.append(str(e))

        return errors

    def list_available_recipes(self) -> List[str]:
        """List all available recipe names"""
        recipes = []

        for pattern in ["*.yml", "*.yaml"]:
            for recipe_file in self.recipe_directory.glob(pattern):
                recipes.append(recipe_file.stem)

        logger.debug(f"Found {len(recipes)} available recipes")
        return sorted(recipes)

    def _find_recipe_file(self, name: str) -> Optional[Path]:
        """Find recipe file by name"""
        for ext in [".yml", ".yaml"]:
            recipe_path = self.recipe_directory / f"{name}{ext}"
            if recipe_path.exists():
                return recipe_path
        return None

    def get_recipe_info(self, name: str) -> Dict:
        """Get basic info about a recipe"""
        recipe_path = self._find_recipe_file(name)
        if not recipe_path:
            return {}

        try:
            import yaml

            with open(recipe_path, "r") as f:
                data = yaml.safe_load(f)

            return {
                "name": data.get("name", name),
                "description": data.get("description", "No description"),
                "file_path": str(recipe_path),
            }
        except Exception as e:
            logger.error(f"Failed to get recipe info: {e}")
            return {}
