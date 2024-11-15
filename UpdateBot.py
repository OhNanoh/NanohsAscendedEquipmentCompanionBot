import requests
import zipfile
import io
import os
import tempfile
import shutil

GITHUB_REPO_ZIP_URL = "https://github.com/OhNanoh/NanohsAscendedEquipmentCompanionBot/archive/refs/heads/main.zip"

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT_PATH = os.path.join(PROJECT_DIR, "NanohsAscendedAccessoriesBot.py")

EXCLUDE_ITEMS = {"update_script.py", "Config"}


def download_and_extract_zip(url, extract_to):
    """
    Downloads a zip file from the given URL, extracts it to a temporary directory,
    and selectively updates the project directory without deleting config files.
    """
    try:
        print("Downloading the latest version...")
        response = requests.get(url)
        response.raise_for_status()

        with tempfile.TemporaryDirectory() as tmpdirname:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                zip_file.extractall(tmpdirname)
                extracted_folder = os.path.join(tmpdirname, os.listdir(tmpdirname)[0])

                for root, dirs, files in os.walk(extracted_folder):
                    rel_path = os.path.relpath(root, extracted_folder)
                    dest_path = os.path.join(extract_to, rel_path)

                    if any(item in rel_path for item in EXCLUDE_ITEMS):
                        continue

                    os.makedirs(dest_path, exist_ok=True)

                    for file in files:
                        if file not in EXCLUDE_ITEMS:
                            src_file = os.path.join(root, file)
                            dest_file = os.path.join(dest_path, file)
                            shutil.copy2(src_file, dest_file)
                            print(f"Updated: {dest_file}")

        print("Update downloaded and applied successfully.")

    except Exception as e:
        print(f"Failed to download or extract the update: {e}")


if __name__ == "__main__":
    download_and_extract_zip(GITHUB_REPO_ZIP_URL, PROJECT_DIR)

