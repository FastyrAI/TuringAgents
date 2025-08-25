#!/usr/bin/env python3
"""
Script to download and cache evaluation datasets.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluations.utils.logging import setup_logging, get_logger

# Dataset configurations
DATASETS = {
    "agentbench": {
        "source": "huggingface",
        "name": "thudm/agentbench",
        "size": "~2GB"
    },
    "swe_bench": {
        "source": "huggingface", 
        "name": "princeton-nlp/swe-bench",
        "size": "~500MB"
    },
    "toolbench": {
        "source": "huggingface",
        "name": "toolbench/toolbench",
        "size": "~1GB"
    },
    "humaneval_x": {
        "source": "huggingface",
        "name": "THUDM/humaneval-x",
        "size": "~100MB"
    },
    "mbpp": {
        "source": "huggingface",
        "name": "mbpp",
        "size": "~50MB"
    },
    "truthfulqa": {
        "source": "huggingface",
        "name": "truthful_qa",
        "size": "~10MB"
    },
    "webarena": {
        "source": "github",
        "name": "web-arena-x/webarena",
        "size": "~3GB"
    },
    "alfworld": {
        "source": "github",
        "name": "alfworld/alfworld",
        "size": "~500MB"
    }
}


def download_huggingface_dataset(name: str, cache_dir: str) -> bool:
    """Download a dataset from Hugging Face."""
    try:
        from datasets import load_dataset
        
        logger = get_logger(__name__)
        logger.info(f"Downloading {name} from Hugging Face...")
        
        # Download and cache the dataset
        dataset = load_dataset(name, cache_dir=cache_dir)
        logger.info(f"Successfully downloaded {name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to download {name}: {str(e)}")
        return False


def download_github_dataset(name: str, cache_dir: str) -> bool:
    """Download a dataset from GitHub."""
    try:
        import subprocess
        
        logger = get_logger(__name__)
        logger.info(f"Cloning {name} from GitHub...")
        
        # Create target directory
        target_dir = Path(cache_dir) / name.split("/")[-1]
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        
        # Clone repository
        subprocess.run([
            "git", "clone", f"https://github.com/{name}.git", str(target_dir)
        ], check=True)
        
        logger.info(f"Successfully cloned {name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to clone {name}: {str(e)}")
        return False


def main():
    """Main function to download datasets."""
    setup_logging()
    logger = get_logger(__name__)
    
    # Get cache directory
    cache_dir = os.getenv("EVALUATIONS_CACHE_DIR", "./cache")
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Downloading datasets to {cache_dir}")
    
    # Track download results
    results = {}
    total_size = 0
    
    for dataset_name, config in DATASETS.items():
        logger.info(f"\n{'='*50}")
        logger.info(f"Downloading {dataset_name} ({config['size']})")
        logger.info(f"{'='*50}")
        
        if config["source"] == "huggingface":
            success = download_huggingface_dataset(config["name"], cache_dir)
        elif config["source"] == "github":
            success = download_github_dataset(config["name"], cache_dir)
        else:
            logger.error(f"Unknown source: {config['source']}")
            success = False
        
        results[dataset_name] = success
    
    # Print summary
    logger.info(f"\n{'='*50}")
    logger.info("Download Summary")
    logger.info(f"{'='*50}")
    
    successful = sum(results.values())
    total = len(results)
    
    for dataset_name, success in results.items():
        status = "✓" if success else "✗"
        logger.info(f"{status} {dataset_name}")
    
    logger.info(f"\nSuccessfully downloaded {successful}/{total} datasets")
    
    if successful < total:
        logger.warning("Some datasets failed to download. Check the logs above for details.")
        sys.exit(1)
    else:
        logger.info("All datasets downloaded successfully!")


if __name__ == "__main__":
    main()