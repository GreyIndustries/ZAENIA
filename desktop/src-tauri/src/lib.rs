use std::{
    env,
    fs,
    path::{Path, PathBuf},
    time::Duration,
};

use serde_json::{
    json,
    Value,
};


const DEFAULT_API_URL: &str = "http://127.0.0.1:8766";
const API_TOKEN_ENV: &str = "ZAENIA_API_TOKEN";
const API_URL_ENV: &str = "ZAENIA_API_URL";
const API_TOKEN_HEADER: &str = "X-ZAENIA-API-TOKEN";
const DESKTOP_KEY_HEADER: &str = "X-ZAENIA-DESKTOP-KEY";
const DESKTOP_KEY_ENV: &str = "ZAENIA_DESKTOP_KEY_FILE";
const NOT_CONNECTED: &str = "This desktop app isn't connected to ZÆNIA yet. At the PC run: python -m core.api.server pair-desktop (it asks for your passkey), then restart the app.";


fn api_base() -> String {
    env::var(API_URL_ENV).unwrap_or_else(|_| DEFAULT_API_URL.to_string())
}


/// Optional: the API token from the ZAENIA_API_TOKEN Windows variable.
fn configured_token() -> Option<String> {
    env::var(API_TOKEN_ENV)
        .ok()
        .map(|token| token.trim().to_string())
        .filter(|token| !token.is_empty())
}


fn desktop_key_path() -> Option<PathBuf> {
    if let Ok(value) = env::var(DESKTOP_KEY_ENV) {
        if !value.trim().is_empty() {
            return Some(PathBuf::from(value.trim()));
        }
    }
    // Windows: %APPDATA%\ZAENIA. Linux: $XDG_CONFIG_HOME/zaenia or ~/.config/zaenia
    // (the same places core/api/desktop_key.py uses).
    if let Ok(appdata) = env::var("APPDATA") {
        return Some(PathBuf::from(appdata).join("ZAENIA").join("desktop_approval.key"));
    }
    let config = env::var("XDG_CONFIG_HOME")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .map(PathBuf::from)
        .or_else(|| env::var("HOME").ok().map(|home| PathBuf::from(home).join(".config")))?;
    Some(config.join("zaenia").join("desktop_approval.key"))
}


/// The desktop key made by `python -m core.api.server pair-desktop` (needs the
/// passkey). It stays in this user's profile; the phone never has it.
fn desktop_key() -> Option<String> {
    let path = desktop_key_path()?;
    let key = fs::read_to_string(path).ok()?;
    let key = key.trim().to_string();
    if key.len() >= 32 {
        Some(key)
    } else {
        None
    }
}


/// Adds whichever credentials this desktop app has. The server accepts the
/// paired desktop key in place of the API token, and needs the key to apply
/// file changes. The credentials never reach the page.
fn with_credentials(request: reqwest::RequestBuilder) -> Result<reqwest::RequestBuilder, String> {
    let token = configured_token();
    let key = desktop_key();
    if token.is_none() && key.is_none() {
        return Err(NOT_CONNECTED.to_string());
    }
    let mut request = request;
    if let Some(token) = token {
        request = request.header(API_TOKEN_HEADER, token);
    }
    if let Some(key) = key {
        request = request.header(DESKTOP_KEY_HEADER, key);
    }
    Ok(request)
}


fn api_error_detail(payload: &Value) -> String {
    match payload.get("detail") {
        Some(Value::String(text)) => text.clone(),
        Some(Value::Array(items)) => items
            .first()
            .and_then(|item| item.get("msg"))
            .and_then(Value::as_str)
            .unwrap_or("The request was not accepted.")
            .to_string(),
        _ => "Unknown API error.".to_string(),
    }
}


async fn call_api(
    method: reqwest::Method,
    path: &str,
    body: Option<Value>,
    timeout_seconds: u64,
) -> Result<Value, String> {
    let api_base = api_base();
    let api_url = format!("{}{}", api_base.trim_end_matches('/'), path);

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(timeout_seconds))
        .build()
        .map_err(|error| format!("Could not create ZÆNIA API client: {}", error))?;

    let mut request = with_credentials(client.request(method, &api_url))?;
    if let Some(payload) = body {
        request = request.json(&payload);
    }

    let response = request
        .send()
        .await
        .map_err(|error| format!("ZÆNIA server is not reachable at {}: {}", api_base, error))?;
    let status = response.status();
    let text = response
        .text()
        .await
        .map_err(|error| format!("Could not read ZÆNIA API response: {}", error))?;
    let payload: Value = if text.trim().is_empty() {
        Value::Null
    } else {
        serde_json::from_str(&text)
            .map_err(|error| format!("ZÆNIA API returned invalid JSON: {}", error))?
    };

    if !status.is_success() {
        return Err(format!(
            "ZÆNIA API error {}: {}",
            status.as_u16(),
            api_error_detail(&payload)
        ));
    }

    Ok(payload)
}


#[tauri::command]
async fn ask_zaenia(message: String) -> Result<String, String> {
    let cleaned = message.trim().to_string();
    if cleaned.is_empty() {
        return Err("Message cannot be empty.".to_string());
    }

    let payload = call_api(
        reqwest::Method::POST,
        "/api/chat",
        Some(json!({ "message": cleaned })),
        150,
    )
    .await?;

    let reply = payload
        .get("reply")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_string();
    if reply.is_empty() {
        return Err("ZÆNIA brain returned an empty reply.".to_string());
    }
    Ok(reply)
}


/// Read-only live status for the UI.
#[tauri::command]
async fn zaenia_status() -> Result<Value, String> {
    call_api(reqwest::Method::GET, "/api/status", None, 8).await
}


/// Generic bridge for the UI's protected routes (tasks, calendar, chat
/// history, speech, voice, system brief, files). Only `/api/` paths on the
/// local ZÆNIA server.
#[tauri::command]
async fn zaenia_api(
    method: String,
    path: String,
    body: Option<Value>,
    desktop: Option<bool>,
) -> Result<Value, String> {
    // The paired desktop key is sent whenever this app has it, so `desktop`
    // only documents which calls need it.
    let _ = desktop;
    let method = match method.to_ascii_uppercase().as_str() {
        "GET" => reqwest::Method::GET,
        "POST" => reqwest::Method::POST,
        "PUT" => reqwest::Method::PUT,
        "PATCH" => reqwest::Method::PATCH,
        "DELETE" => reqwest::Method::DELETE,
        _ => return Err("Unsupported request method.".to_string()),
    };
    let route = path.split('?').next().unwrap_or("");
    if !route.starts_with("/api/")
        || route.contains("..")
        || route.contains("//")
        || path.contains('\\')
        || path.contains('#')
        || path.len() > 2048
    {
        return Err("The desktop bridge only calls ZÆNIA API routes.".to_string());
    }
    let slow = route.starts_with("/api/platform/operator/screen/inspect")
        || route.starts_with("/api/platform/knowledge")
        || route.starts_with("/api/chat")
        || route.starts_with("/api/speak")
        || route.starts_with("/api/voice")
        || route.starts_with("/api/briefing")
        || route.starts_with("/api/calendar")
        || route.starts_with("/api/research");
    // Her research analysis reads long material on the local brain.
    let slowest = route == "/api/research/analyze";
    call_api(method, &path, body, if slowest { 300 } else if slow { 150 } else { 30 }).await
}


/// Briefing WAV through the private desktop bridge; no credential reaches the page.
#[tauri::command]
async fn zaenia_briefing_audio(session_id: String) -> Result<Vec<u8>, String> {
    if session_id.is_empty() || session_id.len() > 100
        || !session_id.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_') {
        return Err("Choose a valid briefing session.".to_string());
    }
    let client = reqwest::Client::builder().timeout(Duration::from_secs(30)).build()
        .map_err(|_| "Could not create the briefing audio client.".to_string())?;
    let url = format!("{}/api/briefing/audio?session_id={}", api_base().trim_end_matches('/'), session_id);
    let mut response = with_credentials(client.get(url))?.send().await
        .map_err(|_| "The briefing audio could not reach this app.".to_string())?;
    let status = response.status();
    if !status.is_success() {
        let payload: Value = response.json().await.unwrap_or(Value::Null);
        return Err(format!("ZÆNIA API error {}: {}", status.as_u16(), api_error_detail(&payload)));
    }
    let mut audio = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| "The briefing audio stopped loading.".to_string())? {
        if audio.len() + chunk.len() > 20 * 1024 * 1024 {
            return Err("The briefing audio is too large.".to_string());
        }
        audio.extend_from_slice(&chunk);
    }
    if audio.len() < 12 || &audio[..4] != b"RIFF" || &audio[8..12] != b"WAVE" {
        return Err("The server did not return valid briefing audio.".to_string());
    }
    Ok(audio)
}

/// Streaming chat: each line ZÆNIA's server sends (start, delta, done,
/// error) is passed to the window as it arrives, so words appear while she
/// is still writing. Stopping goes through POST /api/chat/cancel, which ends
/// this stream on the server side.
#[tauri::command]
async fn zaenia_stream(
    path: String,
    body: Value,
    on_event: tauri::ipc::Channel<Value>,
) -> Result<(), String> {
    if path != "/api/chat/stream" {
        return Err("The desktop bridge only streams ZÆNIA chat.".to_string());
    }
    let api_base = api_base();
    let api_url = format!("{}{}", api_base.trim_end_matches('/'), path);
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(600))
        .build()
        .map_err(|error| format!("Could not create ZÆNIA API client: {}", error))?;

    let request = with_credentials(client.post(&api_url))?.json(&body);
    let mut response = request
        .send()
        .await
        .map_err(|error| format!("ZÆNIA server is not reachable at {}: {}", api_base, error))?;

    let status = response.status();
    if !status.is_success() {
        let text = response.text().await.unwrap_or_default();
        let payload: Value = serde_json::from_str(&text).unwrap_or(Value::Null);
        return Err(format!(
            "ZÆNIA API error {}: {}",
            status.as_u16(),
            api_error_detail(&payload)
        ));
    }

    let mut buffer: Vec<u8> = Vec::new();
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|error| format!("The reply stream stopped: {}", error))?
    {
        buffer.extend_from_slice(&chunk);
        while let Some(end) = buffer.iter().position(|byte| *byte == b'\n') {
            let line: Vec<u8> = buffer.drain(..=end).collect();
            let text = String::from_utf8_lossy(&line);
            let trimmed = text.trim();
            if trimmed.is_empty() {
                continue;
            }
            if let Ok(event) = serde_json::from_str::<Value>(trimmed) {
                on_event
                    .send(event)
                    .map_err(|error| format!("Could not pass the reply to the window: {}", error))?;
            }
        }
    }
    Ok(())
}


#[cfg(windows)]
fn open_voice_window(script: &Path, root: &Path) -> Result<(), String> {
    use std::os::windows::process::CommandExt;
    const CREATE_NEW_CONSOLE: u32 = 0x0000_0010;
    std::process::Command::new("powershell.exe")
        .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
        .arg(script)
        .current_dir(root)
        .creation_flags(CREATE_NEW_CONSOLE)
        .spawn()
        .map_err(|error| format!("Could not open the ZÆNIA Voice window: {}", error))?;
    Ok(())
}

#[cfg(not(windows))]
fn open_voice_window(script: &Path, root: &Path) -> Result<(), String> {
    // scripts/linux/open_zaenia_voice.sh opens a terminal window for the passkey.
    std::process::Command::new("bash")
        .arg(script)
        .current_dir(root)
        .stdin(std::process::Stdio::null())
        .spawn()
        .map_err(|error| format!("Could not open the ZÆNIA Voice window: {}", error))?;
    Ok(())
}

#[cfg(windows)]
const VOICE_SCRIPT: &[&str] = &["scripts", "start_zaenia_voice.ps1"];
#[cfg(not(windows))]
const VOICE_SCRIPT: &[&str] = &["scripts", "linux", "open_zaenia_voice.sh"];


/// Opens the ZÆNIA Voice window on this PC (scripts/start_zaenia_voice.ps1 on
/// Windows, scripts/linux/open_zaenia_voice.sh on Linux).
/// The passkey is typed in that real terminal window, never in the UI.
#[tauri::command]
fn start_voice_service() -> Result<(), String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|desktop| desktop.parent())
        .ok_or_else(|| "Could not find the ZÆNIA project folder.".to_string())?
        .to_path_buf();
    let script = VOICE_SCRIPT.iter().fold(root.clone(), |path, part| path.join(part));
    if !script.is_file() {
        return Err(format!("Voice script not found: {}", script.display()));
    }
    open_voice_window(&script, &root)
}


/// Starts the ZÆNIA API server. "token": hidden, in token mode (API token).
/// "passkey": opens a window where the owner types the passkey (full mode).
#[tauri::command]
fn start_server(mode: String) -> Result<(), String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|desktop| desktop.parent())
        .ok_or_else(|| "Could not find the ZÆNIA project folder.".to_string())?
        .to_path_buf();
    match mode.as_str() {
        "token" => run_restart_script(&root),
        "passkey" => {
            let script = root.join("scripts").join("start_zaenia_server_passkey.ps1");
            if !script.is_file() {
                return Err(format!("Passkey start script not found: {}", script.display()));
            }
            open_voice_window(&script, &root)
                .map_err(|_| "Could not open the ZÆNIA server window for the passkey.".to_string())
        }
        _ => Err("Choose token or passkey.".to_string()),
    }
}

/// Opens the one-time Google Calendar sign-in (the browser asks Zack to Allow).
#[tauri::command]
fn connect_google_calendar() -> Result<(), String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|desktop| desktop.parent())
        .ok_or_else(|| "Could not find the ZÆNIA project folder.".to_string())?
        .to_path_buf();
    let script = root.join("scripts").join("connect_google_calendar.ps1");
    if !script.is_file() {
        return Err(format!("Google connect script not found: {}", script.display()));
    }
    open_voice_window(&script, &root).map_err(|_| "Could not open the Google sign-in window.".to_string())
}

/// Opens the guided voice training (retrain profile, calibrate, refresh app-mic check).
#[tauri::command]
fn open_voice_training() -> Result<(), String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|desktop| desktop.parent())
        .ok_or_else(|| "Could not find the ZÆNIA project folder.".to_string())?
        .to_path_buf();
    let script = root.join("scripts").join("voice_training.ps1");
    if !script.is_file() {
        return Err(format!("Voice training script not found: {}", script.display()));
    }
    open_voice_window(&script, &root).map_err(|_| "Could not open voice training.".to_string())
}

/// Opens the one-time Gmail (read-only) sign-in for important-email summaries.
#[tauri::command]
fn connect_gmail() -> Result<(), String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|desktop| desktop.parent())
        .ok_or_else(|| "Could not find the ZÆNIA project folder.".to_string())?
        .to_path_buf();
    let script = root.join("scripts").join("connect_gmail.ps1");
    if !script.is_file() {
        return Err(format!("Gmail connect script not found: {}", script.display()));
    }
    open_voice_window(&script, &root).map_err(|_| "Could not open the Gmail sign-in window.".to_string())
}

/// Restarts the ZÆNIA API server with the project's own script, hidden.
/// Works even when the server is down, since it doesn't go through the API.
#[tauri::command]
fn restart_server() -> Result<(), String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|desktop| desktop.parent())
        .ok_or_else(|| "Could not find the ZÆNIA project folder.".to_string())?
        .to_path_buf();
    run_restart_script(&root)
}

/// Security-tab owner console: unlocking with the passkey or the spoken phrase,
/// and the passkey-protected security changes. Receives only a fixed mode and,
/// for unlocking, the server's opaque request ID; secrets are typed there, never here.
#[tauri::command]
fn run_security_tool(mode: String, request: Option<String>) -> Result<(), String> {
    const MODES: [&str; 13] = ["unlock_passkey", "unlock_voice", "token_rotate", "token_revoke", "pair_desktop",
        "phrase_setup", "phrase_reset", "mic_change", "mic_reset", "phone_voice_on", "phone_voice_off", "calm_password_setup", "calm_password_reset"];
    let request = request.unwrap_or_default();
    if !MODES.contains(&mode.as_str())
        || (mode.starts_with("unlock_") && (request.len() != 32 || !request.chars().all(|c| c.is_ascii_hexdigit())))
        || (!mode.starts_with("unlock_") && !request.is_empty()) {
        return Err("Choose a security action from the Security tab.".to_string());
    }
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().and_then(|desktop| desktop.parent())
        .ok_or_else(|| "Could not locate the project.".to_string())?;
    let script = root.join("scripts").join("security_console.ps1");
    if !script.is_file() { return Err("The security console is missing.".to_string()); }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let mut command = std::process::Command::new("powershell.exe");
        command.args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]).arg(script).args(["-Mode", &mode]);
        if !request.is_empty() { command.args(["-Request", &request]); }
        command.current_dir(root).creation_flags(0x0000_0010).spawn()
            .map_err(|_| "Could not open the security console.".to_string())?;
        Ok(())
    }
    #[cfg(not(windows))]
    { Err("Run the security commands in an interactive owner terminal on this platform.".to_string()) }
}

/// Fixed local owner console; receives only a mode and an opaque request ID.
#[tauri::command]
fn run_profile_tool(mode: String, request: String) -> Result<(), String> {
    if !["export", "restore", "rollback", "voice_only"].contains(&mode.as_str())
        || request.len() != 32 || !request.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err("Choose a prepared profile request or source snapshot.".to_string());
    }
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().and_then(|desktop| desktop.parent())
        .ok_or_else(|| "Could not locate the project.".to_string())?;
    let script = root.join("scripts").join("profile_console.ps1");
    if !script.is_file() { return Err("The local profile console is missing.".to_string()); }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        std::process::Command::new("powershell.exe")
            .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
            .arg(script).args(["-Mode", &mode, "-Request", &request]).current_dir(root)
            .creation_flags(0x0000_0010).spawn()
            .map_err(|_| "Could not open the owner profile console.".to_string())?;
        Ok(())
    }
    #[cfg(not(windows))]
    { Err("Run the local profile CLI in an interactive owner terminal on this platform.".to_string()) }
}

#[cfg(windows)]
fn run_restart_script(root: &Path) -> Result<(), String> {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let script = root.join("scripts").join("restart_zaenia_server.ps1");
    if !script.is_file() {
        return Err(format!("Restart script not found: {}", script.display()));
    }
    std::process::Command::new("powershell.exe")
        .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
        .arg(&script)
        .current_dir(root)
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .map_err(|error| format!("Could not restart the ZÆNIA server: {}", error))?;
    Ok(())
}

#[cfg(not(windows))]
fn run_restart_script(_root: &Path) -> Result<(), String> {
    Err("Restarting the server from the app is only set up on Windows.".to_string())
}

#[cfg_attr(
    mobile,
    tauri::mobile_entry_point
)]
pub fn run() {
    tauri::Builder::default()
        .plugin(
            tauri_plugin_opener::init()
        )
        .invoke_handler(
            tauri::generate_handler![
                ask_zaenia,
                zaenia_status,
                zaenia_api,
                zaenia_stream,
                start_voice_service,
                restart_server,
                zaenia_briefing_audio,
                start_server,
                connect_google_calendar,
                connect_gmail,
                open_voice_training,
                run_profile_tool,
                run_security_tool
            ]
        )
        .run(
            tauri::generate_context!()
        )
        .expect(
            "error while running tauri application"
        );
}
