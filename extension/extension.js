const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const { spawn, exec } = require('child_process');

const SETTINGS_FILE = 'C:\\Users\\Admin\\.gemini\\config\\jarvis_settings.json';
const SCRIPT_PATH = 'C:\\Users\\Admin\\.gemini\\config\\scripts\\jarvis_speech.py';
const PYTHON_PATH = 'D:\\VoiceStudio\\project\\.venv\\Scripts\\python.exe';
const PROJECT_DIR = 'D:\\VoiceStudio\\project';
const VOICESTUDIO_DATA_DIR = 'D:\\VoiceStudio\\data';
const VOICESTUDIO_MODELS_DIR = 'D:\\VoiceStudio\\models';

function readSettings() {
    const defaults = { enabled: true, speed: 1.2, voice: 'Atul Kapoor' };
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
                    OMNIVOICE_DATA_DIR: VOICESTUDIO_DATA_DIR,
                    OMNIVOICE_CACHE_DIR: VOICESTUDIO_MODELS_DIR
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

    // 1. Mute / Unmute Item
    const muteItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 104);
    muteItem.command = 'jarvis.toggleMute';

    // 2. Stop Button
    const stopItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 103);
    stopItem.command = 'jarvis.stopAudio';
    stopItem.text = '$(debug-stop) Stop';
    stopItem.tooltip = 'Click to silence J.A.R.V.I.S. speech immediately';

    // 3. Speed Selector
    const speedItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 102);
    speedItem.command = 'jarvis.changeSpeed';

    // 4. Replay Button
    const replayItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 101);
    replayItem.command = 'jarvis.replayAudio';
    replayItem.text = '$(history) Replay';
    replayItem.tooltip = 'Click to replay the last assistant message in Atul Kapoor voice';

    // 5. History Browser Button
    const historyItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    historyItem.command = 'jarvis.showHistory';
    historyItem.text = '$(list-unordered) History';
    historyItem.tooltip = 'Browse and speak past conversation turns (Alt+H)';

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
    historyItem.show();

    ensureHeadlessBackend(muteItem);

    if (fs.existsSync(SETTINGS_FILE)) {
        fs.watch(SETTINGS_FILE, () => {
            updateUI();
        });
    }

    // Command: Toggle Mute
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

    // Command: Stop Audio
    const stopAudioCmd = vscode.commands.registerCommand('jarvis.stopAudio', () => {
        exec('taskkill /F /IM ffplay.exe', (err) => {
            if (!err) {
                vscode.window.setStatusBarMessage('$(check) J.A.R.V.I.S. stopped', 2500);
            }
        });
    });

    // Command: Change Speed
    const changeSpeedCmd = vscode.commands.registerCommand('jarvis.changeSpeed', async () => {
        const options = [
            { label: '1.0x', description: 'Original natural speed', value: 1.0 },
            { label: '1.2x', description: 'Comfortable relaxed pace (Recommended)', value: 1.2 },
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

    // Command: Replay Last
    const replayCmd = vscode.commands.registerCommand('jarvis.replayAudio', () => {
        vscode.window.setStatusBarMessage('$(history) Replaying last message...', 3000);
        exec(`python "${SCRIPT_PATH}" --replay`, (err) => {
            if (err) {
                vscode.window.showErrorMessage('Error replaying audio: ' + err.message);
            }
        });
    });

    // Command: Browse Conversation History (Option A)
    const showHistoryCmd = vscode.commands.registerCommand('jarvis.showHistory', () => {
        vscode.window.setStatusBarMessage('$(sync~spin) Loading conversation turns...', 2000);
        exec(`python "${SCRIPT_PATH}" --get-history`, { maxBuffer: 10 * 1024 * 1024 }, async (err, stdout) => {
            if (err || !stdout) {
                vscode.window.showErrorMessage('Could not retrieve conversation history.');
                return;
            }
            try {
                const turns = JSON.parse(stdout);
                if (!turns.length) {
                    vscode.window.showInformationMessage('No conversation messages found in current transcript.');
                    return;
                }
                // Reverse so newest turns are at top, but turn IDs remain stable
                const reversed = turns.slice().reverse();
                const quickPickItems = reversed.map(t => ({
                    label: `${t.role === 'You' ? '$(person)' : '$(robot)'} #${t.id} ${t.role}`,
                    description: t.summary,
                    turnId: t.id
                }));

                const picked = await vscode.window.showQuickPick(quickPickItems, {
                    placeHolder: 'Select a message to speak aloud with Atul Kapoor voice...'
                });

                if (picked) {
                    vscode.window.setStatusBarMessage(`$(unmute) J.A.R.V.I.S.: Speaking turn #${picked.turnId}...`, 4000);
                    exec(`python "${SCRIPT_PATH}" --read-turn ${picked.turnId}`, (playErr) => {
                        if (playErr) {
                            vscode.window.showErrorMessage('Playback error: ' + playErr.message);
                        }
                    });
                }
            } catch (e) {
                vscode.window.showErrorMessage('Error parsing conversation history: ' + e.message);
            }
        });
    });

    // Command: Speak Selected Text (Option C)
    const speakSelectionCmd = vscode.commands.registerCommand('jarvis.speakSelection', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active editor found to read from.');
            return;
        }

        const selection = editor.selection;
        const text = editor.document.getText(selection);

        if (!text || !text.trim()) {
            vscode.window.showWarningMessage('Please highlight/select some text first to speak.');
            return;
        }

        const tempFile = path.join(os.tmpdir(), 'jarvis_speak_selection.txt');
        try {
            fs.writeFileSync(tempFile, text, 'utf8');
        } catch (e) {
            vscode.window.showErrorMessage('Failed to write temporary text file: ' + e.message);
            return;
        }

        vscode.window.setStatusBarMessage('$(unmute) J.A.R.V.I.S.: Synthesizing selected text...', 3500);
        exec(`python "${SCRIPT_PATH}" --speak-file "${tempFile}"`, (err) => {
            if (err) {
                vscode.window.showErrorMessage('Error speaking selection: ' + err.message);
            }
        });
    });

    // Command: Start Backend Manually
    const startBackendCmd = vscode.commands.registerCommand('jarvis.startBackend', () => {
        ensureHeadlessBackend(muteItem);
    });

    context.subscriptions.push(
        muteItem,
        stopItem,
        speedItem,
        replayItem,
        historyItem,
        toggleMuteCmd,
        stopAudioCmd,
        changeSpeedCmd,
        replayCmd,
        showHistoryCmd,
        speakSelectionCmd,
        startBackendCmd
    );
}

function deactivate() {
    exec('taskkill /F /IM ffplay.exe', () => {});
}

module.exports = {
    activate,
    deactivate
};
