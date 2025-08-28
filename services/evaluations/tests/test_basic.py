"""
Basic tests for the evaluations service.
"""

import pytest
import yaml
from pathlib import Path


def test_config_files_exist():
    """Test that configuration files exist and are valid."""
    config_dir = Path(__file__).parent.parent / "configs"
    
    # Check that config files exist
    assert (config_dir / "basic_eval.yaml").exists()
    assert (config_dir / "comprehensive_eval.yaml").exists()
    assert (config_dir / "sample_agent.yaml").exists()


def test_config_files_valid_yaml():
    """Test that configuration files are valid YAML."""
    config_dir = Path(__file__).parent.parent / "configs"
    
    config_files = [
        "basic_eval.yaml",
        "comprehensive_eval.yaml", 
        "sample_agent.yaml"
    ]
    
    for config_file in config_files:
        config_path = config_dir / config_file
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            assert config is not None
            assert isinstance(config, dict)


def test_basic_config_structure():
    """Test that basic config has required structure."""
    config_dir = Path(__file__).parent.parent / "configs"
    
    with open(config_dir / "basic_eval.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    # Check required sections
    assert "benchmarks" in config
    assert "evaluation" in config
    assert "reporting" in config
    assert "logging" in config
    
    # Check benchmarks structure
    assert isinstance(config["benchmarks"], list)
    assert len(config["benchmarks"]) > 0
    
    for benchmark in config["benchmarks"]:
        assert "name" in benchmark
        assert "enabled" in benchmark


def test_agent_config_structure():
    """Test that agent config has required structure."""
    config_dir = Path(__file__).parent.parent / "configs"
    
    with open(config_dir / "sample_agent.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    # Check required sections
    assert "agent" in config
    agent_config = config["agent"]
    
    assert "name" in agent_config
    assert "type" in agent_config
    assert "tools" in agent_config
    assert "safety" in agent_config
    
    # Check tools structure
    assert isinstance(agent_config["tools"], list)
    
    for tool in agent_config["tools"]:
        assert "name" in tool
        assert "description" in tool


def test_package_structure():
    """Test that package structure is correct."""
    src_dir = Path(__file__).parent.parent / "src" / "evaluations"
    
    # Check main package files
    assert (src_dir / "__init__.py").exists()
    assert (src_dir / "cli.py").exists()
    
    # Check subdirectories
    assert (src_dir / "core").is_dir()
    assert (src_dir / "utils").is_dir()
    
    # Check utils
    assert (src_dir / "utils" / "__init__.py").exists()
    assert (src_dir / "utils" / "logging.py").exists()


if __name__ == "__main__":
    pytest.main([__file__])