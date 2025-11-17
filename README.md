# TAI-SEC C2 Panel

Hey there! Welcome to the TAI-SEC C2 Panel, a project born out of the need for a slick, modern, and functional Command and Control panel for remote system management and security testing. This isn't your average command-line tool; it's a full-fledged GUI application built with PyQt6 to make managing multiple targets a breeze.

Think of it as your central dashboard for monitoring and interacting with remote agents, complete with real-time data, a live terminal, and a powerful file manager.

**Disclaimer:**
> This tool is intended for educational purposes and for use in authorized security testing scenarios only. Unauthorized use of this software against systems you do not own or have explicit permission to test is illegal. The developers assume no liability and are not responsible for any misuse or damage caused by this program.

## Features

So, what can this thing actually do?

*   **Modern & Sleek GUI:** Built with PyQt6, featuring a dark theme that's easy on the eyes.
*   **Multi-Target Management:** Easily add, edit, and delete targets. The details are saved locally in `target.json`.
*   **Real-time Status:** A heartbeat mechanism periodically checks if your targets are online or offline, with clear visual indicators.
*   **Live Data Gauges:** See real-time data from the target like CPU usage, network speed (simulated), and signal strength in cool, animated gauges.
*   **Integrated Terminal:** Send shell commands to any selected target and see the output directly in the panel.
*   **Full-Featured File Manager:** Browse the target's file system, upload/download files, create new files/folders, rename, delete, and even edit text files on the fly.
*   **Dynamic PHP Agent:** The `c2.php` agent is what you deploy on the target. It's designed to be lightweight and capable.

## Setup & Installation

Ready to get started? Here’s what you need to do.

1.  **Prerequisites:**
    *   Make sure you have Python 3 installed.
    *   The target machine needs a web server (like Apache or Nginx) with PHP running.

2.  **Clone the Repo:**
    ```bash
    git clone <repository_url>
    cd c2panel
    ```

3.  **Install Dependencies:**
    Install all the necessary Python libraries using the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

## How to Use

### 1. Deploy the Agent

The C2 panel communicates with a PHP agent (`c2.php`) that you need to place on your target's web server.

*   The `c2.php` file in this repository is the agent.
*   You'll need to set a secret **API Key** inside it. Open `c2.php` and replace `___API_KEY___` with a strong, secret key of your choice.
*   Upload this modified `c2.php` file to a web-accessible directory on your target machine.

### 2. Launch the C2 Panel

Run the main application from your terminal:
```bash
python3 main.py
```

### 3. Add a Target

*   Once the panel is open, go to the "Targets" tab.
*   Click the "Add" button.
*   Fill in the details:
    *   **Name:** A friendly name for your target.
    *   **URL:** The full URL to the `c2.php` file you uploaded (e.g., `http://example.com/uploads/c2.php`).
    *   **API Key:** The same secret API key you set in the `c2.php` file.
*   Click "Save". The panel will immediately start checking the target's status.

### 4. Interact with Your Target

*   **Select a Target:** Click on a target in the list to select it.
*   **Use the Terminal:** Go to the "Terminal" tab, type your command, and hit Enter. The output from the target machine will appear above.
*   **Manage Files:** Switch to the "File Manager" tab to explore and manage files on the selected target.
*   **View Gauges:** Click the "Show Gauges" button in the "Targets" tab to see the real-time data visualization.

## Future Plans

This project is still evolving! Here are some of the features on the roadmap:

*   **Process Manager:** View and kill processes running on the target.
*   **DDoS Module:** A (strictly for research) module to understand and simulate different types of DDoS attacks.
*   **Enhanced Stealth:** More features to make C2 communication harder to detect.
*   **Agent Persistence:** Mechanisms to ensure the agent stays active on the target.

---
Happy (and ethical) hacking!
