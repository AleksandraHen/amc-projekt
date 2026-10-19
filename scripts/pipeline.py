
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = PROJECT_ROOT / "tests"


steps = [
    ("Load dataset", SCRIPTS_DIR / "load_dataset.py"),
    ("Clean dataset", SCRIPTS_DIR / "clean_dataset.py"),
    ("Gold standard tests", TESTS_DIR / "gold_standard.py"),
    ("Feature engineering", SCRIPTS_DIR / "feature_engineering.py"),
    ("Instrument validation", SCRIPTS_DIR / "instrument_validation.py"),
]


def main():

    for step_number, (step_name, script_path) in enumerate( steps, start=1):

        print(f"[{step_number}/{len(steps)}] {step_name}")
        subprocess.run([sys.executable, str(script_path)],cwd=PROJECT_ROOT,check=True,)
        print(f"Completed: {step_name}")


if __name__ == "__main__":
    main()