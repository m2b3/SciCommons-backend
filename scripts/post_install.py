import subprocess


def main():
    try:
        result = subprocess.run(["pre-commit", "install"], check=True)
        if result.returncode == 0:
            print("pre-commit hooks installed successfully.")
        else:
            print("Failed to install pre-commit hooks.")
    except Exception as e:
        print(f"An error occurred: {e}")
