import requests
import os
import tkinter as tk
from tkinter import messagebox

class AppWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto Updater")
        self.geometry("400x300")

        self.log_text = tk.Text(self, wrap=tk.WORD)
        self.log_text.pack(expand=True, fill=tk.BOTH)

        self.check_updates_button = tk.Button(self, text="Check for Updates", command=self.check_for_updates)
        self.check_updates_button.pack(pady=10)

    def append_to_log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def send_notification(self, title, message, icon):
        messagebox.showinfo(title, message)

    def check_for_updates(self):
        """Check for updates from GitHub and download the latest release if available."""
        repo_owner = "your-username"
        repo_name = "your-repo-name"
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"

        try:
            response = requests.get(api_url)
            response.raise_for_status()
            latest_release = response.json()
            latest_version = latest_release["tag_name"]
            download_url = latest_release["assets"][0]["browser_download_url"]

            current_version = "v1.0.0"  # Replace with your current version

            if latest_version != current_version:
                self.append_to_log(f"New version available: {latest_version}. Downloading update...")
                self.download_update(download_url)
            else:
                self.append_to_log("You are already using the latest version.")

        except requests.RequestException as e:
            self.append_to_log(f"Error checking for updates: {str(e)}")

    def download_update(self, url):
        """Download the update from the given URL."""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            update_file_path = "/c:/Users/LA GAMING PC/Desktop/autoupdater/autoupdate_new.py"  # Replace with the desired path
            with open(update_file_path, "wb") as update_file:
                for chunk in response.iter_content(chunk_size=8192):
                    update_file.write(chunk)

            self.append_to_log("Update downloaded successfully. Please restart the application to apply the update.")
            self.send_notification("Update Downloaded", "Please restart the application to apply the update.", "dialog-information")

        except requests.RequestException as e:
            self.append_to_log(f"Error downloading update: {str(e)}")

if __name__ == "__main__":
    app = AppWindow()
    app.mainloop()