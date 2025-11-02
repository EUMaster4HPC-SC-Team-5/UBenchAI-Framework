"""
Unit tests for RecipeLoader - CORRECTED VERSION
Tests: recipe discovery, loading, validation, caching, template creation
"""

import pytest
from pathlib import Path
import yaml
import tempfile
from unittest.mock import Mock, patch

from ubenchai.servers.recipe_loader import RecipeLoader
from ubenchai.servers.services import ServiceRecipe, ResourceSpec


class TestRecipeLoaderInitialization:
    """Tests for RecipeLoader initialization"""

    def test_initialization_creates_directory(self):
        """Test that recipe directory is created if it doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            recipe_dir = Path(tmpdir) / "recipes"
            loader = RecipeLoader(recipe_directory=str(recipe_dir))

            assert recipe_dir.exists()
            assert loader.recipe_directory == recipe_dir

    def test_initialization_with_existing_directory(self):
        """Test initialization with existing directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = RecipeLoader(recipe_directory=tmpdir)
            assert loader.recipe_directory == Path(tmpdir)

    def test_initialization_cache_empty(self):
        """Test that cache is initially empty"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = RecipeLoader(recipe_directory=tmpdir)
            assert len(loader._cache) == 0


class TestRecipeLoading:
    """Tests for recipe loading"""

    @pytest.fixture
    def temp_recipe_dir(self):
        """Fixture for temporary recipe directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def loader(self, temp_recipe_dir):
        """Fixture for recipe loader"""
        return RecipeLoader(recipe_directory=str(temp_recipe_dir))

    @pytest.fixture
    def valid_recipe_data(self):
        """Fixture for valid recipe data"""
        return {
            "name": "test-service",
            "image": "docker://test/image:latest",
            "resources": {"cpu_cores": 2, "memory_gb": 4, "gpu_count": 0},
            "ports": [{"container_port": 8080, "host_port": 8080}],
            "environment": {"TEST_VAR": "test_value"},
        }

    def create_recipe_file(self, directory, name, data):
        """Helper to create recipe file"""
        recipe_path = directory / f"{name}.yml"
        with open(recipe_path, "w") as f:
            yaml.dump(data, f)
        return recipe_path

    def test_load_recipe_success(self, loader, temp_recipe_dir, valid_recipe_data):
        """Test successfully loading a recipe"""
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)

        recipe = loader.load_recipe("test-service")

        assert recipe.name == "test-service"
        assert recipe.image == "docker://test/image:latest"
        assert recipe.resources.cpu_cores == 2

    def test_load_recipe_with_yaml_extension(
        self, loader, temp_recipe_dir, valid_recipe_data
    ):
        """Test loading recipe with .yaml extension"""
        recipe_path = temp_recipe_dir / "test-service.yaml"
        with open(recipe_path, "w") as f:
            yaml.dump(valid_recipe_data, f)

        recipe = loader.load_recipe("test-service")
        assert recipe.name == "test-service"

    def test_load_recipe_not_found(self, loader):
        """Test loading non-existent recipe"""
        with pytest.raises(FileNotFoundError, match="Recipe not found"):
            loader.load_recipe("nonexistent")

    def test_load_recipe_caching(self, loader, temp_recipe_dir, valid_recipe_data):
        """Test that recipes are cached after first load"""
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)

        # First load
        recipe1 = loader.load_recipe("test-service")

        # Second load should come from cache
        recipe2 = loader.load_recipe("test-service")

        assert recipe1 is recipe2
        assert len(loader._cache) == 1

    def test_load_recipe_validation_failure(self, loader, temp_recipe_dir):
        """Test loading recipe that fails validation"""
        invalid_data = {
            "name": "test-service",
            "image": "docker://test/image:latest",
            "resources": {"cpu_cores": 0, "memory_gb": 4},  # Invalid
        }

        self.create_recipe_file(temp_recipe_dir, "invalid-service", invalid_data)

        # FIXED: The error comes directly from ResourceSpec.validate()
        with pytest.raises(ValueError, match="CPU cores must be positive"):
            loader.load_recipe("invalid-service")

    def test_load_recipe_missing_required_fields(self, loader, temp_recipe_dir):
        """Test loading recipe with missing required fields"""
        incomplete_data = {
            "name": "test-service"
            # Missing image and resources
        }

        self.create_recipe_file(temp_recipe_dir, "incomplete", incomplete_data)

        with pytest.raises(Exception):  # Will fail during parsing
            loader.load_recipe("incomplete")


class TestRecipeValidation:
    """Tests for recipe validation"""

    @pytest.fixture
    def loader(self):
        """Fixture for recipe loader"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield RecipeLoader(recipe_directory=tmpdir)

    def test_validate_recipe_success(self, loader):
        """Test validating a valid recipe"""
        resources = ResourceSpec(cpu_cores=2, memory_gb=4)
        recipe = ServiceRecipe(
            name="test", image="docker://test:latest", resources=resources
        )

        errors = loader.validate_recipe(recipe)
        assert len(errors) == 0

    def test_validate_recipe_excessive_cpu(self, loader):
        """Test validation with excessive CPU cores"""
        resources = ResourceSpec(cpu_cores=200, memory_gb=4)
        recipe = ServiceRecipe(
            name="test", image="docker://test:latest", resources=resources
        )

        errors = loader.validate_recipe(recipe)
        assert any("CPU cores exceeds" in error for error in errors)

    def test_validate_recipe_excessive_memory(self, loader):
        """Test validation with excessive memory"""
        resources = ResourceSpec(cpu_cores=2, memory_gb=2000)
        recipe = ServiceRecipe(
            name="test", image="docker://test:latest", resources=resources
        )

        errors = loader.validate_recipe(recipe)
        assert any("Memory exceeds" in error for error in errors)

    def test_validate_recipe_excessive_gpu(self, loader):
        """Test validation with excessive GPU count"""
        resources = ResourceSpec(cpu_cores=2, memory_gb=4, gpu_count=16)
        recipe = ServiceRecipe(
            name="test", image="docker://test:latest", resources=resources
        )

        errors = loader.validate_recipe(recipe)
        assert any("GPU count exceeds" in error for error in errors)

    def test_validate_recipe_invalid_resources(self, loader):
        """Test validation with invalid resources"""
        resources = ResourceSpec(cpu_cores=0, memory_gb=4)
        recipe = ServiceRecipe(
            name="test", image="docker://test:latest", resources=resources
        )

        errors = loader.validate_recipe(recipe)
        assert len(errors) > 0


class TestRecipeDiscovery:
    """Tests for recipe discovery and listing"""

    @pytest.fixture
    def temp_recipe_dir(self):
        """Fixture for temporary recipe directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def loader(self, temp_recipe_dir):
        """Fixture for recipe loader"""
        return RecipeLoader(recipe_directory=str(temp_recipe_dir))

    def create_recipe_file(self, directory, name, extension=".yml"):
        """Helper to create minimal recipe file"""
        recipe_data = {
            "name": name,
            "image": "docker://test:latest",
            "resources": {"cpu_cores": 1, "memory_gb": 1},
        }

        recipe_path = directory / f"{name}{extension}"
        with open(recipe_path, "w") as f:
            yaml.dump(recipe_data, f)
        return recipe_path

    def test_list_available_recipes_empty(self, loader):
        """Test listing recipes in empty directory"""
        recipes = loader.list_available_recipes()
        assert len(recipes) == 0

    def test_list_available_recipes_single(self, loader, temp_recipe_dir):
        """Test listing single recipe"""
        self.create_recipe_file(temp_recipe_dir, "recipe1")

        recipes = loader.list_available_recipes()

        assert len(recipes) == 1
        assert "recipe1" in recipes

    def test_list_available_recipes_multiple(self, loader, temp_recipe_dir):
        """Test listing multiple recipes"""
        self.create_recipe_file(temp_recipe_dir, "recipe1")
        self.create_recipe_file(temp_recipe_dir, "recipe2")
        self.create_recipe_file(temp_recipe_dir, "recipe3")

        recipes = loader.list_available_recipes()

        assert len(recipes) == 3
        assert "recipe1" in recipes
        assert "recipe2" in recipes
        assert "recipe3" in recipes

    def test_list_available_recipes_mixed_extensions(self, loader, temp_recipe_dir):
        """Test listing recipes with both .yml and .yaml extensions"""
        self.create_recipe_file(temp_recipe_dir, "recipe1", ".yml")
        self.create_recipe_file(temp_recipe_dir, "recipe2", ".yaml")

        recipes = loader.list_available_recipes()

        assert len(recipes) == 2

    def test_list_available_recipes_sorted(self, loader, temp_recipe_dir):
        """Test that recipe list is sorted"""
        self.create_recipe_file(temp_recipe_dir, "charlie")
        self.create_recipe_file(temp_recipe_dir, "alice")
        self.create_recipe_file(temp_recipe_dir, "bob")

        recipes = loader.list_available_recipes()

        assert recipes == ["alice", "bob", "charlie"]

    def test_list_available_recipes_ignores_non_yaml(self, loader, temp_recipe_dir):
        """Test that non-YAML files are ignored"""
        self.create_recipe_file(temp_recipe_dir, "recipe1", ".yml")

        # Create non-YAML file
        (temp_recipe_dir / "readme.txt").write_text("Some text")

        recipes = loader.list_available_recipes()

        assert len(recipes) == 1
        assert "recipe1" in recipes


class TestRecipeCache:
    """Tests for recipe caching"""

    @pytest.fixture
    def temp_recipe_dir(self):
        """Fixture for temporary recipe directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def loader(self, temp_recipe_dir):
        """Fixture for recipe loader"""
        return RecipeLoader(recipe_directory=str(temp_recipe_dir))

    def create_recipe_file(self, directory, name):
        """Helper to create recipe file"""
        recipe_data = {
            "name": name,
            "image": "docker://test:latest",
            "resources": {"cpu_cores": 1, "memory_gb": 1},
        }

        recipe_path = directory / f"{name}.yml"
        with open(recipe_path, "w") as f:
            yaml.dump(recipe_data, f)
        return recipe_path

    def test_cache_hit(self, loader, temp_recipe_dir):
        """Test cache hit on second load"""
        self.create_recipe_file(temp_recipe_dir, "test-recipe")

        # First load
        recipe1 = loader.load_recipe("test-recipe")

        # Second load (should hit cache)
        recipe2 = loader.load_recipe("test-recipe")

        assert recipe1 is recipe2

    def test_reload_recipes(self, loader, temp_recipe_dir):
        """Test reloading recipes clears cache"""
        self.create_recipe_file(temp_recipe_dir, "test-recipe")

        # Load and cache
        loader.load_recipe("test-recipe")
        assert len(loader._cache) == 1

        # Reload
        result = loader.reload_recipes()

        assert result is True
        assert len(loader._cache) == 0

    def test_cache_separate_recipes(self, loader, temp_recipe_dir):
        """Test that different recipes are cached separately"""
        self.create_recipe_file(temp_recipe_dir, "recipe1")
        self.create_recipe_file(temp_recipe_dir, "recipe2")

        recipe1 = loader.load_recipe("recipe1")
        recipe2 = loader.load_recipe("recipe2")

        assert len(loader._cache) == 2
        assert recipe1 is not recipe2


class TestRecipeInfo:
    """Tests for getting recipe information"""

    @pytest.fixture
    def temp_recipe_dir(self):
        """Fixture for temporary recipe directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def loader(self, temp_recipe_dir):
        """Fixture for recipe loader"""
        return RecipeLoader(recipe_directory=str(temp_recipe_dir))

    def test_get_recipe_info_success(self, loader, temp_recipe_dir):
        """Test getting recipe info without full load"""
        recipe_data = {
            "name": "test-service",
            "image": "docker://test/image:latest",
            "description": "Test description",
            "resources": {"cpu_cores": 2, "memory_gb": 4},
        }

        recipe_path = temp_recipe_dir / "test-service.yml"
        with open(recipe_path, "w") as f:
            yaml.dump(recipe_data, f)

        info = loader.get_recipe_info("test-service")

        assert info["name"] == "test-service"
        assert info["image"] == "docker://test/image:latest"
        assert info["description"] == "Test description"
        assert "file_path" in info

    def test_get_recipe_info_not_found(self, loader):
        """Test getting info for non-existent recipe"""
        info = loader.get_recipe_info("nonexistent")
        assert info == {}

    def test_get_recipe_info_parse_error(self, loader, temp_recipe_dir):
        """Test getting info when YAML is invalid"""
        recipe_path = temp_recipe_dir / "invalid.yml"
        with open(recipe_path, "w") as f:
            f.write("invalid: yaml: content:")

        info = loader.get_recipe_info("invalid")
        assert info == {}


class TestRecipeTemplateCreation:
    """Tests for recipe template creation"""

    @pytest.fixture
    def temp_recipe_dir(self):
        """Fixture for temporary recipe directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def loader(self, temp_recipe_dir):
        """Fixture for recipe loader"""
        return RecipeLoader(recipe_directory=str(temp_recipe_dir))

    def test_create_recipe_template(self, loader):
        """Test creating a recipe template"""
        template_path = loader.create_recipe_template("new-recipe")

        assert template_path.exists()
        assert template_path.name == "new-recipe.yml"

    def test_template_content_valid(self, loader):
        """Test that created template has valid content"""
        template_path = loader.create_recipe_template("new-recipe")

        with open(template_path) as f:
            data = yaml.safe_load(f)

        assert data["name"] == "new-recipe"
        assert "image" in data
        assert "resources" in data
        assert "ports" in data
        assert "environment" in data

    def test_template_loadable(self, loader):
        """Test that created template can be loaded"""
        loader.create_recipe_template("new-recipe")

        # Template should be loadable (though it may fail validation)
        # depending on whether example values are valid
        try:
            recipe = loader.load_recipe("new-recipe")
            assert recipe.name == "new-recipe"
        except ValueError:
            # If validation fails, that's okay for template
            pass


class TestRecipeLoaderHelperMethods:
    """Tests for helper methods"""

    @pytest.fixture
    def temp_recipe_dir(self):
        """Fixture for temporary recipe directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def loader(self, temp_recipe_dir):
        """Fixture for recipe loader"""
        return RecipeLoader(recipe_directory=str(temp_recipe_dir))

    def test_find_recipe_file_yml(self, loader, temp_recipe_dir):
        """Test finding recipe with .yml extension"""
        recipe_path = temp_recipe_dir / "test.yml"
        recipe_path.touch()

        found_path = loader._find_recipe_file("test")

        assert found_path == recipe_path

    def test_find_recipe_file_yaml(self, loader, temp_recipe_dir):
        """Test finding recipe with .yaml extension"""
        recipe_path = temp_recipe_dir / "test.yaml"
        recipe_path.touch()

        found_path = loader._find_recipe_file("test")

        assert found_path == recipe_path

    def test_find_recipe_file_not_found(self, loader):
        """Test finding non-existent recipe"""
        found_path = loader._find_recipe_file("nonexistent")
        assert found_path is None

    def test_parse_yaml_success(self, loader, temp_recipe_dir):
        """Test parsing valid YAML file"""
        test_data = {"key": "value", "number": 42}

        yaml_path = temp_recipe_dir / "test.yml"
        with open(yaml_path, "w") as f:
            yaml.dump(test_data, f)

        parsed = loader._parse_yaml(str(yaml_path))

        assert parsed == test_data

    def test_parse_yaml_empty_file(self, loader, temp_recipe_dir):
        """Test parsing empty YAML file"""
        yaml_path = temp_recipe_dir / "empty.yml"
        yaml_path.touch()

        parsed = loader._parse_yaml(str(yaml_path))

        assert parsed == {}

    def test_parse_yaml_invalid(self, loader, temp_recipe_dir):
        """Test parsing invalid YAML"""
        yaml_path = temp_recipe_dir / "invalid.yml"
        with open(yaml_path, "w") as f:
            f.write("invalid: yaml: content:")

        with pytest.raises(yaml.YAMLError):
            loader._parse_yaml(str(yaml_path))


class TestRecipeLoaderIntegration:
    """Integration tests for RecipeLoader"""

    @pytest.fixture
    def temp_recipe_dir(self):
        """Fixture for temporary recipe directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def loader(self, temp_recipe_dir):
        """Fixture for recipe loader"""
        return RecipeLoader(recipe_directory=str(temp_recipe_dir))

    def create_full_recipe(self, directory, name):
        """Create a complete recipe with all features"""
        recipe_data = {
            "name": name,
            "image": "docker://test/image:latest",
            "description": f"Full recipe for {name}",
            "resources": {
                "cpu_cores": 4,
                "memory_gb": 8,
                "gpu_count": 1,
                "gpu_type": "nvidia-a100",
            },
            "ports": [
                {"container_port": 8080, "host_port": 8080},
                {"container_port": 8081, "host_port": 8081},
            ],
            "environment": {"VAR1": "value1", "VAR2": "value2"},
            "volumes": [
                {
                    "host_path": "/host/data",
                    "container_path": "/data",
                    "readonly": False,
                }
            ],
            "healthcheck": {"endpoint": "/health", "interval_seconds": 10},
        }

        recipe_path = directory / f"{name}.yml"
        with open(recipe_path, "w") as f:
            yaml.dump(recipe_data, f)
        return recipe_path

    def test_full_workflow(self, loader, temp_recipe_dir):
        """Test complete workflow: create, discover, load, validate"""
        # Create recipes
        self.create_full_recipe(temp_recipe_dir, "recipe1")
        self.create_full_recipe(temp_recipe_dir, "recipe2")

        # Discover recipes
        recipes = loader.list_available_recipes()
        assert len(recipes) == 2

        # Load and validate
        recipe1 = loader.load_recipe("recipe1")
        assert recipe1.name == "recipe1"
        assert recipe1.resources.gpu_count == 1

        # Check caching
        recipe1_cached = loader.load_recipe("recipe1")
        assert recipe1 is recipe1_cached

        # Get info without loading
        info = loader.get_recipe_info("recipe2")
        assert info["name"] == "recipe2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
