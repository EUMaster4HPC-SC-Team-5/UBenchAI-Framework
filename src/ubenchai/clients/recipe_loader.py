"""
ClientRecipeLoader - Manages discovery, loading, and validation of client recipes
"""

from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger
import yaml

from ubenchai.clients.recipes import ClientRecipe


class ClientRecipeLoader:
    """
    Manages discovery, parsing, and validation of client recipes from the filesystem.
    Provides schema validation and error reporting.
    """

    def __init__(self, recipe_directory: str = "recipes/clients"):
        """
        Initialize ClientRecipeLoader

        Args:
            recipe_directory: Directory containing client recipe YAML files
        """
        self.recipe_directory = Path(recipe_directory)
        self._cache: Dict[str, ClientRecipe] = {}

        # Create directory if it doesn't exist
        self.recipe_directory.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"ClientRecipeLoader initialized with directory: {self.recipe_directory}"
        )

    def load_recipe(self, name: str) -> ClientRecipe:
        """
        Load a client recipe by name

        Args:
            name: Name of the recipe (without .yml extension)

        Returns:
            ClientRecipe instance

        Raises:
            FileNotFoundError: If recipe file not found
            ValueError: If recipe validation fails
        """
        # Check cache first
        if name in self._cache:
            logger.debug(f"Loading recipe from cache: {name}")
            return self._cache[name]

        # Look for recipe file
        recipe_path = self._find_recipe_file(name)
        if not recipe_path:
            raise FileNotFoundError(f"Recipe not found: {name}")

        # Load and validate recipe
        recipe = ClientRecipe.from_yaml(str(recipe_path))

        # Validate
        errors = self.validate_recipe(recipe)
        if errors:
            error_msg = f"Recipe validation failed for {name}: {', '.join(errors)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Cache it
        self._cache[name] = recipe
        logger.info(f"Loaded and cached recipe: {name}")

        return recipe

    def validate_recipe(self, recipe: ClientRecipe) -> List[str]:
        """
        Validate a recipe

        Args:
            recipe: ClientRecipe to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        try:
            recipe.validate()
        except ValueError as e:
            errors.append(str(e))

        # Additional validation checks
        if recipe.workload.concurrent_users > 1000:
            errors.append("Concurrent users exceeds reasonable limit (1000)")

        if recipe.workload.duration_seconds > 3600:
            errors.append("Duration exceeds reasonable limit (1 hour)")

        return errors

    def list_available_recipes(self) -> List[str]:
        """
        List all available recipe names

        Returns:
            List of recipe names (without .yml extension)
        """
        recipes = []

        # Find all .yml and .yaml files
        for pattern in ["*.yml", "*.yaml"]:
            for recipe_file in self.recipe_directory.glob(pattern):
                recipe_name = recipe_file.stem
                recipes.append(recipe_name)

        logger.debug(f"Found {len(recipes)} available recipes")
        return sorted(recipes)

    def reload_recipes(self) -> bool:
        """
        Clear cache and reload all recipes

        Returns:
            True if reload successful
        """
        self._cache.clear()
        logger.info("Recipe cache cleared")
        return True

    def _find_recipe_file(self, name: str) -> Optional[Path]:
        """
        Find recipe file by name

        Args:
            name: Recipe name

        Returns:
            Path to recipe file if found, None otherwise
        """
        # Try both .yml and .yaml extensions
        for ext in [".yml", ".yaml"]:
            recipe_path = self.recipe_directory / f"{name}{ext}"
            if recipe_path.exists():
                return recipe_path

        return None

    def get_recipe_info(self, name: str) -> Dict:
        """
        Get basic info about a recipe without fully loading it

        Args:
            name: Recipe name

        Returns:
            Dictionary with basic recipe information
        """
        recipe_path = self._find_recipe_file(name)
        if not recipe_path:
            return {}

        try:
            with open(recipe_path, "r") as f:
                data = yaml.safe_load(f)

            return {
                "name": data.get("name", name),
                "description": data.get("description", "No description"),
                "file_path": str(recipe_path),
                "target_service": data.get("target", {}).get("service", "unknown"),
                "workload_pattern": data.get("workload", {}).get(
                    "pattern", "unknown"
                ),
            }
        except Exception as e:
            logger.error(f"Failed to get recipe info for {name}: {e}")
            return {}

    def create_recipe_template(self, name: str) -> Path:
        """
        Create a template recipe file

        Args:
            name: Name for the new recipe

        Returns:
            Path to created template file
        """
        template = {
            "name": name,
            "description": "Example client benchmark recipe",
            "target": {
                "service": "ollama-llm",
                "protocol": "http",
                "timeout_seconds": 30,
            },
            "workload": {
                "pattern": "closed-loop",
                "duration_seconds": 60,
                "concurrent_users": 10,
                "think_time_ms": 100,
            },
            "dataset": {
                "type": "synthetic",
                "params": {"prompt_length": 100, "num_prompts": 100},
            },
            "orchestration": {
                "mode": "slurm",
                "resources": {"cpu_cores": 1, "memory_gb": 4},
            },
            "output": {
                "metrics": ["latency", "throughput", "errors"],
                "format": "json",
                "destination": "./results",
            },
        }

        output_path = self.recipe_directory / f"{name}.yml"

        with open(output_path, "w") as f:
            yaml.dump(template, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Created recipe template: {output_path}")
        return output_path