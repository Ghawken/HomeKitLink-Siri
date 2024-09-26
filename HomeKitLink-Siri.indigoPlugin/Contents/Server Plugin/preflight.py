# preflight.py

# preflight.py

import subprocess
import os
import sys
from pathlib import Path
import time

import indigo  # Assume indigo is always available

def install_xcode_tools():
    try:
        installation_output = ""  # Initialize installation output
        current_directory = Path.cwd()  # Current directory
        parent_directory = current_directory.parent  # Parent directoryrent directory
        plugin_path = current_directory  # Assuming pluginPath is current_directory

        # Construct the relative path to the pip-install-log-success.txt file
        relative_path = os.path.join("..", "Packages", "pip-install-log-success.txt")  # Add ".." to go up one directory
        # Construct the absolute path to the target file
        file_path = os.path.normpath(os.path.join(plugin_path, relative_path))

        # Check if the pip-install-log-success.txt file exists
        if os.path.exists(file_path):
            message = f"✅ Libraries correctly installed: Based on: {file_path}"
            indigo.server.log(message)
            installation_output += message + "\n"

            message = "✅ Xcode Command Line Tools are not needed. Skipping installation."
            indigo.server.log(message)
            installation_output += message + "\n"

            return installation_output  # Exit the function since Xcode tools are not needed

        message = f"❌ 'pip-install-log-success.txt' not found at: {file_path}"
        indigo.server.log(message)
        installation_output += message + "\n"

        message = "🔍 Proceeding to check for Xcode Command Line Tools..."
        indigo.server.log(message)
        installation_output += message + "\n"

        # Proceed to check for Xcode Command Line Tools
        try:
            result = subprocess.run(
                ['xcode-select', '-p'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            developer_path = result.stdout.strip()
            if result.returncode == 0 and os.path.exists(developer_path):
                message = f"✅ Xcode Command Line Tools are installed at: {developer_path}"
                indigo.server.log(message)
                installation_output += message + "\n"
            else:
                message = "❌ Xcode Command Line Tools are NOT installed."
                indigo.server.log(message)
                installation_output += message + "\n"

                message = "❌ This may cause issues with compiling library dependencies and plugin failure. Attempting to install..."
                indigo.server.log(message)
                installation_output += message + "\n"

                try:
                    # Initiate the installation
                    subprocess.run(['xcode-select', '--install'], check=True)
                    message = "✅ Initiated installation of Xcode Command Line Tools.  "
                    indigo.server.log(message)
                    installation_output += message + "\n"

                    # Delay plugin startup and restart after installation is likely complete
                    delay_seconds = 600  # Adjust as needed (e.g., 300 seconds = 5 minutes)
                    message = f"⏳ Waiting {delay_seconds} seconds for installation to complete..."
                    indigo.server.log(message)
                    installation_output += message + "\n"

                    time.sleep(delay_seconds)

                    message = "🔄 Restarting plugin to complete installation."
                    indigo.server.log(message)
                    installation_output += message + "\n"

                    # Restart the plugin
                    indigo.server.restartPlugin("com.GlennNZ.indigoplugin.HomeKitLink-Siri")

                    # Exit after initiating restart
                    sys.exit(0)

                except Exception as e:
                    message = f"❌ Failed to initiate Xcode Command Line Tools installation: {e}"
                    indigo.server.log(message)
                    installation_output += message + "\n"

                    message = "❌ Please run 'xcode-select --install' from a Terminal."
                    indigo.server.log(message)
                    installation_output += message + "\n"

                    message = "ℹ️ See Forum Post Xcode tools sticky for more options."
                    indigo.server.log(message)
                    installation_output += message + "\n"

        except Exception as e:
            message = f"❌ Error checking Xcode Command Line Tools: {e}"
            indigo.server.log(message)
            installation_output += message + "\n"

        return installation_output  # Return the collected installation output
    except:
        indigo.server.log("Exception Caught in Xcode Preflight check. Skipped.")
