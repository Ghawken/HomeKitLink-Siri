# dependency_checker.py

import os
from pathlib import Path
import subprocess

# Attempt to import indigo for logging
try:
    import indigo
    INDIGO_AVAILABLE = True
except ImportError:
    INDIGO_AVAILABLE = False
    print("⚠️ Indigo library not found. Falling back to print statements for logging.")

def log(message):
    """
    Logs messages using indigo.server.log if available, otherwise prints to console.
    """
    if INDIGO_AVAILABLE:
        indigo.server.log(message)
    else:
        print(message)

def install_xcode_tools():
    """
    Checks for Xcode Command Line Tools and attempts installation if missing.
    """
    try:
        result = subprocess.run(
            ['xcode-select', '-p'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        developer_path = result.stdout.strip()
        if result.returncode == 0 and os.path.exists(developer_path):
            log(f"✅ Xcode Command Line Tools are installed at: {developer_path}")
            log("✅ Continuing Plugin Startup, Library install Failure has another basis")
            return True
        else:
            log("❌ Xcode Command Line Tools are NOT installed.")
            log("❌ This may cause issues with compiling library dependencies and plugin failure. Attempting to install...")
            try:
                subprocess.run(['xcode-select', '--install'], check=True)
                log("✅ Initiated installation of Xcode Command Line Tools.")
                log("✅ Please complete the installation dialog and restart the plugin once done.")
            except Exception as e:
                log(f"❌ Failed to install Xcode Command Line Tools: {e}")
                log("❌ Please run 'xcode-select --install' from a Terminal.")
                log("ℹ️ Refer to the forum post on Xcode tools for more options.")
            return False
    except Exception as e:
        log(f"❌ Error checking Xcode Command Line Tools: {e}")
        return False

def check_dependencies():
    """
    Performs dependency checks and handles missing dependencies.
    """
    # Define paths
    """
        Performs dependency checks and handles missing dependencies.
        Looks for any file whose name ends with 'pip-install-log-success.txt'
        """

    plugin_path = Path.cwd()
    packages_dir = (plugin_path / ".." / "Packages").resolve()

    # Match any file ending with the target name
    success_files = list(packages_dir.glob("*pip-install-log-success.txt"))

    if not success_files:
        messages = [
            f"❌ No file ending with 'pip-install-log-success.txt' found in: {packages_dir}",
            "❌ This means that libraries have not been installed correctly.",
            "❌ (and there is likely a lot of error messaging above)",
            "❌ Commonly this is because compiler tools are needed for some dependencies.",
            "❌ Initiating check for this ... Once completed Restart Plugin"
        ]

        for message in messages:
            log(message)

        if not install_xcode_tools():
            log("❌ Dependency checks failed. Plugin will not start.")
            raise RuntimeError("❌ Dependency checks failed. Plugin will not start.")

    else:
        log(f"✅ Found dependency success marker: {success_files[0].name}")
        log("✅ ✅ Confirmed Library Installs have been successfully Completed ✅ ✅")
# Run the dependency checks upon import
check_dependencies()
