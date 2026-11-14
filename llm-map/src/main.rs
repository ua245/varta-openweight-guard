//! Step 1 — llm-map
//!
//! Inventories local open-weight / open-source LLM processes on this machine
//! and writes `llm_map.json` for the proxy (Step 2).
//!
//! This binary does NOT enforce policy. The proxy owns enforcement.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::net::TcpStream;
use std::path::PathBuf;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use sysinfo::{ProcessesToUpdate, System};

const KNOWN_NAMES: &[&str] = &[
    "ollama",
    "ollama.exe",
    "vllm",
    "llama-server",
    "llama-server.exe",
    "llama_cpp",
    "text-generation-server",
    "text-generation-launcher",
    "lmstudio",
    "lm-studio",
    "localai",
    "local-ai",
    "gpt4all",
    "koboldcpp",
    "koboldcpp.exe",
    "tabbyapi",
    "aphrodite",
    "sglang",
    "mlx_lm",
    "llamafile",
];

const KNOWN_CMDLINE_MARKERS: &[&str] = &[
    "ollama",
    "vllm.entrypoints",
    "vllm serve",
    "llama-server",
    "llama.cpp",
    "text-generation-inference",
    "lmstudio",
    "localai",
    "koboldcpp",
    "tabbyapi",
    "sglang",
    "mlx_lm.server",
    "openai_compatible",
    "uvicorn",
];

/// Common OpenAI-compatible bind ports to probe when a process is suspected.
const CANDIDATE_PORTS: &[u16] = &[
    11434, // Ollama
    8000,  // vLLM / many servers
    8080,  // llama.cpp server / TGI
    5000,  // miscellaneous
    5001,  // LocalAI
    1234,  // LM Studio
    3000,  // alternate
    8888,  // alternate
];

#[derive(Debug, Serialize, Deserialize, Clone)]
struct LlmEndpoint {
    pid: u32,
    name: String,
    cmdline: String,
    ports: Vec<u16>,
    base_url: Option<String>,
    models: Vec<String>,
    openai_compatible: bool,
    notes: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct LlmMap {
    generated_at_unix: u64,
    hostname: String,
    /// Canonical product surface — coding agents must use the proxy, not these backends.
    proxy_notice: String,
    endpoints: Vec<LlmEndpoint>,
}

fn now_unix() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn looks_like_llm(name: &str, cmdline: &str) -> bool {
    let name_l = name.to_ascii_lowercase();
    let cmd_l = cmdline.to_ascii_lowercase();
    KNOWN_NAMES.iter().any(|n| name_l == *n || name_l.contains(n))
        || KNOWN_CMDLINE_MARKERS
            .iter()
            .any(|m| cmd_l.contains(m))
}

fn extract_ports_from_cmdline(cmdline: &str) -> Vec<u16> {
    let mut ports = Vec::new();
    let lower = cmdline.to_ascii_lowercase();
    // --port 8080 / -p 8080 / :8080 / port=8080
    for token in lower.split(|c: char| c.is_whitespace() || c == '=' || c == ',') {
        let t = token.trim_start_matches(':');
        if let Ok(p) = t.parse::<u16>() {
            if (1024..=65535).contains(&p) {
                ports.push(p);
            }
        }
    }
    // Also catch --port8080 style miss
    for marker in ["--port", "-port", "port"] {
        if let Some(idx) = lower.find(marker) {
            let rest = &lower[idx + marker.len()..];
            let digits: String = rest
                .chars()
                .skip_while(|c| !c.is_ascii_digit())
                .take_while(|c| c.is_ascii_digit())
                .collect();
            if let Ok(p) = digits.parse::<u16>() {
                if (1024..=65535).contains(&p) {
                    ports.push(p);
                }
            }
        }
    }
    ports.sort_unstable();
    ports.dedup();
    ports
}

fn port_open(port: u16) -> bool {
    TcpStream::connect_timeout(
        &format!("127.0.0.1:{port}").parse().unwrap(),
        Duration::from_millis(120),
    )
    .is_ok()
}

fn probe_openai(base: &str) -> (bool, Vec<String>, Vec<String>) {
    let mut notes = Vec::new();
    let url = format!("{}/v1/models", base.trim_end_matches('/'));
    let agent = ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_millis(400))
        .timeout_read(Duration::from_millis(800))
        .build();
    match agent.get(&url).call() {
        Ok(resp) => {
            let body: Result<serde_json::Value, _> = resp.into_json();
            match body {
                Ok(v) => {
                    let models = v
                        .get("data")
                        .and_then(|d| d.as_array())
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|m| m.get("id").and_then(|i| i.as_str()).map(str::to_string))
                                .collect::<Vec<_>>()
                        })
                        .unwrap_or_default();
                    (true, models, notes)
                }
                Err(e) => {
                    notes.push(format!("/v1/models returned non-JSON: {e}"));
                    (true, Vec::new(), notes)
                }
            }
        }
        Err(e) => {
            notes.push(format!("probe {url} failed: {e}"));
            (false, Vec::new(), notes)
        }
    }
}

fn discover() -> Vec<LlmEndpoint> {
    let mut sys = System::new_all();
    sys.refresh_processes(ProcessesToUpdate::All, true);

    let mut by_pid: BTreeMap<u32, LlmEndpoint> = BTreeMap::new();

    for (pid, proc_) in sys.processes() {
        let name = proc_.name().to_string_lossy().to_string();
        let cmdline = proc_
            .cmd()
            .iter()
            .map(|s| s.to_string_lossy().to_string())
            .collect::<Vec<_>>()
            .join(" ");
        if !looks_like_llm(&name, &cmdline) {
            continue;
        }
        let mut ports = extract_ports_from_cmdline(&cmdline);
        // Default Ollama port if name matches and nothing parsed
        if ports.is_empty() && name.to_ascii_lowercase().contains("ollama") {
            ports.push(11434);
        }
        by_pid.insert(
            pid.as_u32(),
            LlmEndpoint {
                pid: pid.as_u32(),
                name,
                cmdline,
                ports,
                base_url: None,
                models: Vec::new(),
                openai_compatible: false,
                notes: Vec::new(),
            },
        );
    }

    // Probe candidate ports; attach open ones to matching processes or as orphans.
    let mut open_ports: Vec<u16> = CANDIDATE_PORTS
        .iter()
        .copied()
        .filter(|p| port_open(*p))
        .collect();
    for ep in by_pid.values() {
        for p in &ep.ports {
            if port_open(*p) && !open_ports.contains(p) {
                open_ports.push(*p);
            }
        }
    }
    open_ports.sort_unstable();
    open_ports.dedup();

    // Enrich known processes with reachable base URLs
    for ep in by_pid.values_mut() {
        let mut try_ports = ep.ports.clone();
        for p in &open_ports {
            if !try_ports.contains(p) {
                try_ports.push(*p);
            }
        }
        for port in try_ports {
            let base = format!("http://127.0.0.1:{port}");
            let (ok, models, notes) = probe_openai(&base);
            ep.notes.extend(notes);
            if ok {
                ep.base_url = Some(base);
                ep.models = models;
                ep.openai_compatible = true;
                if !ep.ports.contains(&port) {
                    ep.ports.push(port);
                }
                break;
            }
        }
    }

    // Orphan OpenAI-compatible listeners with no matched process
    let claimed: Vec<u16> = by_pid
        .values()
        .filter_map(|e| e.base_url.as_ref())
        .filter_map(|u| u.rsplit(':').next()?.parse().ok())
        .collect();
    for port in open_ports {
        if claimed.contains(&port) {
            continue;
        }
        let base = format!("http://127.0.0.1:{port}");
        let (ok, models, notes) = probe_openai(&base);
        if ok {
            by_pid.insert(
                0 + port as u32, // synthetic key for orphans (port-based)
                LlmEndpoint {
                    pid: 0,
                    name: format!("openai-compatible@{port}"),
                    cmdline: String::new(),
                    ports: vec![port],
                    base_url: Some(base),
                    models,
                    openai_compatible: true,
                    notes,
                },
            );
        }
    }

    by_pid.into_values().collect()
}

fn output_path() -> PathBuf {
    if let Some(p) = env::args().nth(1) {
        return PathBuf::from(p);
    }
    // Default: repo-root llm_map.json when run from llm-map/, else cwd
    let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if cwd.ends_with("llm-map") {
        cwd.parent()
            .unwrap_or(&cwd)
            .join("llm_map.json")
    } else {
        cwd.join("llm_map.json")
    }
}

fn main() {
    let endpoints = discover();
    let map = LlmMap {
        generated_at_unix: now_unix(),
        hostname: hostname(),
        proxy_notice: "Backends listed here are for the PROXY only. Coding agents must set base_url to the proxy (Step 2), never call these endpoints directly. All future features land in proxy/."
            .into(),
        endpoints,
    };

    let path = output_path();
    let json = serde_json::to_string_pretty(&map).expect("serialize llm_map");
    fs::write(&path, format!("{json}\n")).unwrap_or_else(|e| {
        eprintln!("failed to write {}: {e}", path.display());
        std::process::exit(1);
    });

    println!("wrote {} ({} endpoint(s))", path.display(), map.endpoints.len());
    for ep in &map.endpoints {
        let url = ep.base_url.as_deref().unwrap_or("(no openai /v1 yet)");
        println!(
            "  pid={} name={} openai={} models={} url={}",
            ep.pid,
            ep.name,
            ep.openai_compatible,
            ep.models.len(),
            url
        );
    }
}

fn hostname() -> String {
    System::host_name().unwrap_or_else(|| "unknown".into())
}
