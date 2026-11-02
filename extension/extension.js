const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawn, exec } = require('child_process');

const SETTINGS_FILE = 'C:\\Users\\Admin\\.gemini\\config\\jarvis_settings.json';
const SCRIPT_PATH = 'C:\\Users\\Admin\\.gemini\\config\\scripts\\jarvis_speech.py';
const PYTHON_PATH = 'D:\\VoiceStudio\\project\\.venv\\Scripts\\python.exe';
const PROJECT_DIR = 'D:\\VoiceStudio\\project';

function readSettings() {
    const defaults = { enabled: true, speed: 1.35, voice: 'Atul Kapoor' };
    if (fs.existsSync(SETTINGS_FILE)) {
        try {
            const raw = fs.readFileSync(SETTINGS_FILE, 'utf8');
            return Object.assign(defaults, JSON.parse(raw));
        } catch (e) {
            console.error('Error reading jarvis_settings.json:', e);
        }
    }
    return defaults;
}

function writeSettings(settings) {
    try {
        const dir = path.dirname(SETTINGS_FILE);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        fs.writeFileSync(SETTINGS_FILE, JSON.stringify(settings, null, 2), 'utf8');
    } catch (e) {
        console.error('Error writing jarvis_settings.json:', e);
    }
}

function checkBackendHealth() {
    return new Promise((resolve) => {
        const req = http.get('http://127.0.0.1:3900/health', { timeout: 1500 }, (res) => {
            resolve(res.statusCode === 200);
        });
        req.on('error', () => resolve(false));
        req.on('timeout', () => { req.destroy(); resolve(false); });
    });
}

function ensureHeadlessBackend(statusBarItem) {
    checkBackendHealth().then((isHealthy) => {
        if (isHealthy) {
            return;
        }

        if (!fs.existsSync(PYTHON_PATH)) {
            vscode.window.showWarningMessage('VoiceStudio Python environment not found on D: drive.');
            return;
        }

        if (statusBarItem) {
            statusBarItem.text = '$(sync~spin) JARVIS: Starting...';
        }

        const child = spawn(
            PYTHON_PATH,
            ['-m', 'uvicorn', 'main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '3900'],
            {
                cwd: PROJECT_DIR,
                detached: true,
                stdio: 'ignore',
                windowsHide: true,
                env: Object.assign({}, process.env, {
                    OMNIVOICE_DATA_DIR: 'D:\\VoiceStudio\\data',
                    OMNIVOICE_CACHE_DIR: 'D:\\VoiceStudio\\models'
                })
            }
        );
        child.unref();

        let attempts = 0;
        const interval = setInterval(async () => {
            attempts++;
            const healthy = await checkBackendHealth();
            if (healthy) {
                clearInterval(interval);
                vscode.window.setStatusBarMessage('$(check) J.A.R.V.I.S. voice engine ready (headless)', 3500);
                if (statusBarItem) {
                    const settings = readSettings();
                    statusBarItem.text = settings.enabled ? '$(unmute) JARVIS: ON' : '$(mute) JARVIS: OFF';
                }
            } else if (attempts > 30) {
                clearInterval(interval);
                if (statusBarItem) {
                    statusBarItem.text = '$(error) JARVIS: Error';
                }
            }
        }, 1000);
    });
}

function activate(context) {
    let settings = readSettings();

    // 1. Mute / Unmute Status Bar Item
    const muteItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 103);
    muteItem.command = 'jarvis.toggleMute';

    // 2. Stop Button Status Bar Item
    const stopItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 102);
    stopItem.command = 'jarvis.stopAudio';
    stopItem.text = '$(debug-stop) Stop';
    stopItem.tooltip = 'Click to silence J.A.R.V.I.S. speech immediately';

    // 3. Speed Control Status Bar Item
    const speedItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 101);
    speedItem.command = 'jarvis.changeSpeed';

    // 4. Replay Button Status Bar Item
    const replayItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    replayItem.command = 'jarvis.replayAudio';
    replayItem.text = '$(history) Replay';
    replayItem.tooltip = 'Click to replay the last assistant message in Atul Kapoor voice';

    function updateUI() {
        settings = readSettings();
        if (settings.enabled) {
            muteItem.text = '$(unmute) JARVIS: ON';
            muteItem.tooltip = 'J.A.R.V.I.S. voice is active. Click to MUTE.';
            muteItem.backgroundColor = undefined;
        } else {
            muteItem.text = '$(mute) JARVIS: OFF';
            muteItem.tooltip = 'J.A.R.V.I.S. voice is muted. Click to UNMUTE.';
            muteItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        }
        const speedVal = Number(settings.speed);
        speedItem.text = `$(dashboard) ${speedVal.toFixed(speedVal % 1 === 0 ? 1 : 2)}x`;
        speedItem.tooltip = `Current speed is ${speedVal}x. Click to change.`;
    }

    updateUI();
    muteItem.show();
    stopItem.show();
    speedItem.show();
    replayItem.show();

    // Automatically check and start headless backend on IDE boot!
    ensureHeadlessBackend(muteItem);

    // Watch for external setting file changes
    if (fs.existsSync(SETTINGS_FILE)) {
        fs.watch(SETTINGS_FILE, () => {
            updateUI();
        });
    }

    // Register Command: Toggle Mute
    const toggleMuteCmd = vscode.commands.registerCommand('jarvis.toggleMute', () => {
        settings = readSettings();
        settings.enabled = !settings.enabled;
        writeSettings(settings);
        updateUI();

        if (!settings.enabled) {
            exec('taskkill /F /IM ffplay.exe', () => {});
            vscode.window.showInformationMessage('J.A.R.V.I.S. voice is now MUTED');
        } else {
            vscode.window.showInformationMessage('J.A.R.V.I.S. voice is now ON');
        }
    });

    // Register Command: Stop Speech
    const stopAudioCmd = vscode.commands.registerCommand('jarvis.stopAudio', () => {
        exec('taskkill /F /IM ffplay.exe', (err) => {
            if (!err) {
                vscode.window.setStatusBarMessage('$(check) J.A.R.V.I.S. stopped', 2500);
            }
        });
    });

    // Register Command: Change Speed
    const changeSpeedCmd = vscode.commands.registerCommand('jarvis.changeSpeed', async () => {
        const options = [
            { label: '1.0x', description: 'Original natural speed', value: 1.0 },
            { label: '1.2x', description: 'Comfortable relaxed pace', value: 1.2 },
            { label: '1.35x', description: 'Brisk & productive', value: 1.35 },
            { label: '1.5x', description: 'Fast pace', value: 1.5 },
            { label: '1.75x', description: 'Very fast pace', value: 1.75 },
            { label: '2.0x', description: 'Double speed', value: 2.0 }
        ];

        const selected = await vscode.window.showQuickPick(options, {
            placeHolder: `Select J.A.R.V.I.S. voice playback speed (current: ${settings.speed}x)`
        });

        if (selected) {
            settings = readSettings();
            settings.speed = selected.value;
            writeSettings(settings);
            updateUI();
            vscode.window.showInformationMessage(`J.A.R.V.I.S. speed set to ${selected.value}x`);
        }
    });

    // Register Command: Replay
    const replayCmd = vscode.commands.registerCommand('jarvis.replayAudio', () => {
        vscode.window.setStatusBarMessage('$(history) Replaying last message...', 3000);
        exec(`python "${SCRIPT_PATH}" --replay`, (err) => {
            if (err) {
                vscode.window.showErrorMessage('Error replaying audio: ' + err.message);
            }
        });
    });

    // Register Command: Start Backend Manually
    const startBackendCmd = vscode.commands.registerCommand('jarvis.startBackend', () => {
        ensureHeadlessBackend(muteItem);
    });

    context.subscriptions.push(muteItem, stopItem, speedItem, replayItem, toggleMuteCmd, stopAudioCmd, changeSpeedCmd, replayCmd, startBackendCmd);
}

function deactivate() {
    exec('taskkill /F /IM ffplay.exe', () => {});
}

module.exports = {
    activate,
    deactivate
};
