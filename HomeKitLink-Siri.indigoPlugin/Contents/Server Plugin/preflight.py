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
    current_directory = Path.cwd()  # Current directory
    parent_directory = current_directory.parent  # Parent directory
    plugin_path = current_directory  # Assuming pluginPath is current_directory

    # Construct the relative path to the pip-install-log-success.txt file
    relative_path = os.path.join("..", "Packages", "pip-install-log-success.txt")  # Add ".." to go up one directory

    # Construct the absolute path to the target file
    file_path = os.path.normpath(os.path.join(plugin_path, relative_path))

    if not os.path.exists(file_path):
        messages = [
            f"❌ 'pip-install-log-success.txt' not found at: {file_path}",
            "❌ This means that libraries have not been installed correctly. (and there is likely a lot of error messaging above)",
            "❌ Commonly this is because compiler tools are needed for some dependencies. This is a fairly big Xcode download, but only needs to be done once.",
            "❌ Initiating check for this ...  Once completed Restart Plugin"
        ]

        for message in messages:
            log(message)

        # Attempt to install Xcode Command Line Tools
        if not install_xcode_tools():
            log("❌ Dependency checks failed. Plugin will not start.")
            # Optionally, you can raise an exception to halt further execution
            raise RuntimeError("❌ Dependency checks failed. Plugin will not start.")
    else:
        log("✅ ✅  Confirmed Library Installs have been successfully Completed  ✅ ✅ ")
# Run the dependency checks upon import
check_dependencies()
