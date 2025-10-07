"""
RecipeLoader - Manages discovery, loading, and validation of service recipes
"""

from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger
import yaml

from ubenchai.servers.services import ServiceRecipe


class RecipeLoader:
    """
    Manages discovery, validation, and loading of service recipes from filesystem
    """

    def __init__(self, recipe_directory: str = "recipes"):
        """
        Initialize RecipeLoader

        Args:
            recipe_directory: Directory containing recipe YAML files
        """
        self.recipe_directory = Path(recipe_directory)
        self._cache: Dict[str, ServiceRecipe] = {}

        # Create directory if it doesn't exist
        self.recipe_directory.mkdir(parents=True, exist_ok=True)

        logger.info(f"RecipeLoader initialized with directory: {self.recipe_directory}")

    def load_recipe(self, name: str) -> ServiceRecipe:
        """
        Load a recipe by name

        Args:
            name: Name of the recipe (without .yml extension)

        Returns:
            ServiceRecipe instance

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
        recipe = ServiceRecipe.from_yaml(str(recipe_path))

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

    def validate_recipe(self, recipe: ServiceRecipe) -> List[str]:
        """
        Validate a recipe

        Args:
            recipe: ServiceRecipe to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        try:
            recipe.validate()
        except ValueError as e:
            errors.append(str(e))

        # Additional validation checks
        if recipe.resources.cpu_cores > 128:
            errors.append("CPU cores exceeds reasonable limit (128)")

        if recipe.resources.memory_gb > 1024:
            errors.append("Memory exceeds reasonable limit (1TB)")

        if recipe.resources.gpu_count > 8:
            errors.append("GPU count exceeds reasonable limit (8)")

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

    def _parse_yaml(self, file_path: str) -> Dict:
        """
        Parse YAML file

        Args:
            file_path: Path to YAML file

        Returns:
            Parsed YAML as dictionary

        Raises:
            yaml.YAMLError: If parsing fails
        """
        with open(file_path, "r") as f:
            try:
                data = yaml.safe_load(f)
                return data if data else {}
            except yaml.YAMLError as e:
                logger.error(f"Failed to parse YAML file {file_path}: {e}")
                raise

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
            data = self._parse_yaml(str(recipe_path))
            return {
                "name": data.get("name", name),
                "image": data.get("image", "unknown"),
                "description": data.get("description", "No description"),
                "file_path": str(recipe_path),
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
            "image": "docker://example/image:latest",
            "description": "Example service recipe",
            "resources": {
                "cpu_cores": 1,
                "memory_gb": 1,
                "gpu_count": 0,
            },
            "ports": [
                {
                    "container_port": 8080,
                    "host_port": 8080,
                }
            ],
            "environment": {
                "EXAMPLE_VAR": "example_value",
            },
            "volumes": [],
            "healthcheck": {
                "endpoint": "/health",
                "interval_seconds": 10,
                "timeout_seconds": 5,
                "retries": 3,
                "initial_delay": 5,
            },
        }

        output_path = self.recipe_directory / f"{name}.yml"

        with open(output_path, "w") as f:
            yaml.dump(template, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Created recipe template: {output_path}")
        return output_path
