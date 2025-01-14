import os
import asyncio
import aiohttp
import signal
import requests
import sys
import json
import subprocess
import pytz
import semver
import tkinter as tk
from datetime import datetime
from dotenv import load_dotenv
from tkinter import messagebox
from threading import Thread
from alive_progress import alive_bar
from loguru import logger

# Configure logger
logger.remove()
logger.add("roblox_monitor.log", level="DEBUG", rotation="1 MB", compression="zip")
logger.add(sys.stdout, level="INFO")

# Load environment variables
load_dotenv()

# Configuration
AVATAR_URL = "https://img.icons8.com/plasticine/2x/robux.png"
UPDATEEVERY = 60
TIMEZONE = pytz.timezone("America/New_York")
TRANSACTION_DATA_PATH = "transaction_data.json"
ROBUX_BALANCE_PATH = "robux_balance.json"

# Global variables
DISCORD_WEBHOOK_URL = ""
USERID = ""
COOKIES = {}
TRANSACTION_API_URL = ""
CURRENCY_API_URL = ""
shutdown_flag = False
monitoring_thread = None

# Signal handling
def signal_handler(signal, frame):
    global shutdown_flag
    logger.info("Shutting down...")
    shutdown_flag = True

signal.signal(signal.SIGINT, signal_handler)

# Utility functions
def load_json_data(filepath, default_data):
    if os.path.exists(filepath):
        with open(filepath, 'r') as file:
            return json.load(file)
    return default_data

def save_json_data(filepath, data):
    with open(filepath, 'w') as file:
        json.dump(data, file, indent=4)

def get_current_time():
    return datetime.now(TIMEZONE).strftime('%m/%d/%Y %I:%M:%S %p')

async def send_discord_notification(embed):
    payload = {
        "embeds": [embed],
        "username": "Roblox Monitor",
        "avatar_url": AVATAR_URL
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30) as response:
                response.raise_for_status()
                logger.info("Notification sent successfully.")
        except aiohttp.ClientError as e:
            logger.error(f"Error sending notification: {e}")

async def fetch_data(url):
    retries = 3
    async with aiohttp.ClientSession() as session:
        for _ in range(retries):
            try:
                async with session.get(url, cookies=COOKIES, timeout=30) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                logger.error(f"Error fetching data from {url}: {e}")
                await asyncio.sleep(5)
    return None

async def fetch_transaction_data():
    return await fetch_data(TRANSACTION_API_URL)

async def fetch_robux_balance():
    response = await fetch_data(CURRENCY_API_URL)
    return response.get("robux", 0) if response else 0

async def monitor(gui_vars):
    last_transaction_data = load_json_data(TRANSACTION_DATA_PATH, {})
    last_robux_balance = load_json_data(ROBUX_BALANCE_PATH, {"robux": 0})

    with alive_bar(title="Monitoring Roblox Data", spinner="dots_waves") as bar:
        while not shutdown_flag:
            current_transaction_data, current_robux_balance = await asyncio.gather(
                fetch_transaction_data(),
                fetch_robux_balance()
            )

            gui_vars["robux_balance"].set(f"Current Robux Balance: {current_robux_balance}")

            if current_transaction_data:
                changes = {
                    key: (last_transaction_data.get(key, 0), current_transaction_data[key])
                    for key in current_transaction_data if current_transaction_data[key] != last_transaction_data.get(key, 0)
                }

                if changes:
                    await send_discord_notification({
                        "title": "\U0001F514 Roblox Transaction Update",
                        "description": "Transaction changes detected.",
                        "fields": [
                            {"name": key, "value": f"**{old}** -> **{new}**", "inline": False}
                            for key, (old, new) in changes.items()
                        ],
                        "color": 720640,
                        "footer": {"text": f"Detected at {get_current_time()}"}
                    })
                    last_transaction_data.update(current_transaction_data)
                    save_json_data(TRANSACTION_DATA_PATH, last_transaction_data)

            robux_change = current_robux_balance - last_robux_balance["robux"]
            if robux_change != 0:
                change_type = "gained" if robux_change > 0 else "spent"
                color = 0x00FF00 if robux_change > 0 else 0xFF0000
                await send_discord_notification({
                    "title": "\U0001F4B8 Robux Balance Update",
                    "description": f"You have {change_type} Robux.",
                    "fields": [
                        {"name": "Previous Balance", "value": f"**{last_robux_balance['robux']}**", "inline": True},
                        {"name": "Current Balance", "value": f"**{current_robux_balance}**", "inline": True},
                        {"name": "Change", "value": f"**{'+' if robux_change > 0 else ''}{robux_change}**", "inline": True}
                    ],
                    "color": color,
                    "footer": {"text": f"Detected at {get_current_time()}"}
                })
                last_robux_balance["robux"] = current_robux_balance
                save_json_data(ROBUX_BALANCE_PATH, last_robux_balance)

            bar()
            await asyncio.sleep(UPDATEEVERY)

def start_monitoring(gui_vars):
    global DISCORD_WEBHOOK_URL, USERID, COOKIES, TRANSACTION_API_URL, CURRENCY_API_URL, monitoring_thread

    DISCORD_WEBHOOK_URL = gui_vars["discord_webhook"].get()
    USERID = gui_vars["user_id"].get()
    COOKIES[".ROBLOSECURITY"] = gui_vars["roblox_cookies"].get()

    TRANSACTION_API_URL = f"https://economy.roblox.com/v2/users/{USERID}/transaction-totals?timeFrame=Year&transactionType=summary"
    CURRENCY_API_URL = f"https://economy.roblox.com/v1/users/{USERID}/currency"

    if not DISCORD_WEBHOOK_URL or not USERID or not COOKIES[".ROBLOSECURITY"]:
        messagebox.showerror("Error", "Please fill in all the fields!")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    monitoring_thread = Thread(target=lambda: loop.run_until_complete(monitor(gui_vars)))
    monitoring_thread.start()

def create_gui():
    root = tk.Tk()
    root.title("Roblox Monitoring")

    gui_vars = {
        "robux_balance": tk.StringVar(value="Current Robux Balance: 0"),
        "discord_webhook": tk.StringVar(),
        "user_id": tk.StringVar(),
        "roblox_cookies": tk.StringVar()
    }

    tk.Label(root, text="Discord Webhook URL").pack(pady=5)
    tk.Entry(root, textvariable=gui_vars["discord_webhook"], width=50).pack(pady=5)

    tk.Label(root, text="Roblox User ID").pack(pady=5)
    tk.Entry(root, textvariable=gui_vars["user_id"], width=50).pack(pady=5)

    tk.Label(root, text="Roblox Cookies").pack(pady=5)
    tk.Entry(root, textvariable=gui_vars["roblox_cookies"], width=50).pack(pady=5)

    tk.Label(root, textvariable=gui_vars["robux_balance"], font=("Arial", 14)).pack(pady=20)

    tk.Button(root, text="Start Monitoring", command=lambda: Thread(target=start_monitoring, args=(gui_vars,)).start()).pack(pady=10)

    def stop_monitoring():
        global shutdown_flag, monitoring_thread
        shutdown_flag = True
        if monitoring_thread:
            monitoring_thread.join()

    tk.Button(root, text="Stop Monitoring", command=stop_monitoring).pack(pady=10)

    def check_for_updates():
        logger.info("Checking for updates...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(check_for_updates_periodically())

    tk.Button(root, text="Check for Updates", command=check_for_updates).pack(pady=10)

    root.mainloop()

async def check_for_updates_periodically():
    current_version = "v0.1.0"  # Your current version
    repo_owner = "MrAndiGamesDev"
    repo_name = "remake-roblox-transaction"
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"

    while not shutdown_flag:
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            latest_release = response.json()

            latest_version = latest_release["tag_name"].strip()  # Make sure to strip spaces
            download_url = latest_release["assets"][0]["browser_download_url"]

            # Use semver to compare versions properly
            if semver.compare(latest_version, current_version) > 0:  # If the latest version is greater
                logger.info(f"New version available: {latest_version}.")
                if messagebox.askyesno("Update Available", f"A new version ({latest_version}) is available. Do you want to download it?"):
                    download_update(download_url)
                else:
                    logger.info("User chose not to download the update.")
            else:
                logger.info("You are already using the latest version.")
                messagebox.showinfo("No Updates", "You are already using the latest version of the application.")
        except requests.RequestException as e:
            logger.error(f"Error checking for updates: {e}")

def download_update(url):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        update_file_path = "robloxtransaction.py"
        with open(update_file_path, 'wb') as update_file:
            for chunk in response.iter_content(chunk_size=8192):
                update_file.write(chunk)

        os.replace(update_file_path, "robloxtransaction.py")
        logger.info("Update downloaded and applied.")
        subprocess.Popen(["python", "robloxtransaction.py"])
        sys.exit()
    except requests.RequestException as e:
        logger.error(f"Error downloading update: {e}")

def main():
    loop = asyncio.get_event_loop()
    loop.create_task(check_for_updates_periodically())
    create_gui()

if __name__ == "__main__":
    main()
