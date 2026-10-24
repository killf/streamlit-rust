//! S01-S12: private resolver inputs avoid changing global CWD/environment.
//! The subprocess test below additionally calls the actual production start().
use super::*;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

struct TempDirectory(PathBuf);

impl TempDirectory {
    fn new() -> Self {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../target/static-tests").join(uuid::Uuid::new_v4().to_string());
        fs::create_dir_all(&root).unwrap();
        Self(fs::canonicalize(root).unwrap())
    }

    fn join(&self, name: &str) -> PathBuf {
        self.0.join(name)
    }
}

impl Drop for TempDirectory {
    fn drop(&mut self) {
        // Only the fresh UUID directory created by this test; remove_dir_all
        // does not traverse directory symlinks. Child guards are dropped first.
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn minimal_bundle(root: &Path) {
    fs::create_dir_all(root).unwrap();
    fs::write(root.join("index.html"), OFFICIAL_INDEX).unwrap();
    for name in boot_assets() {
        let path = root.join(name);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        // These are availability fixtures, never packaged/browser evidence.
        fs::write(path, b"test availability").unwrap();
    }
}

fn repository_markers(root: &Path) {
    for name in ["Cargo.toml", "streamlit/Cargo.toml", "streamlit-macros/Cargo.toml"] {
        let path = root.join(name);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, b"test repository marker").unwrap();
    }
}

fn resolve(builder: Option<&Path>, environment: Option<&Path>, executable: &Path, cwd: &Path, debug: bool) -> io::Result<StaticDirectory> {
    resolve_static_dir(builder, environment, || Ok(executable.to_path_buf()), cwd, debug)
}

fn error(result: io::Result<StaticDirectory>) -> io::Error {
    result.err().expect("invalid assets must not select a fallback")
}

#[test]
fn s01_builder_wins_without_even_probing_executable() {
    let temp = TempDirectory::new();
    minimal_bundle(&temp.join("builder"));
    minimal_bundle(&temp.join("environment"));
    minimal_bundle(&temp.join("www"));
    let chosen = resolve_static_dir(Some(Path::new("builder")), Some(&temp.join("environment")), || panic!("builder must not probe executable"), &temp.0, true).unwrap();
    assert_eq!(chosen.path, fs::canonicalize(temp.join("builder")).unwrap());
    assert_eq!(chosen.source, "builder");
}

#[test]
fn s02_relative_environment_wins_without_executable_probe() {
    let temp = TempDirectory::new();
    minimal_bundle(&temp.join("environment"));
    minimal_bundle(&temp.join("www"));
    let chosen = resolve_static_dir(None, Some(Path::new("environment")), || panic!("environment must not probe executable"), &temp.0, true).unwrap();
    assert_eq!(chosen.path, fs::canonicalize(temp.join("environment")).unwrap());
    assert_eq!(chosen.source, "STREAMLIT_STATIC_DIR");
}

#[test]
fn s03_executable_sidecar_beats_unrelated_cwd_www() {
    let temp = TempDirectory::new();
    minimal_bundle(&temp.join("install/www"));
    minimal_bundle(&temp.join("cwd/www"));
    let chosen = resolve(None, None, &temp.join("install/app.exe"), &temp.join("cwd"), false).unwrap();
    assert_eq!(chosen.path, fs::canonicalize(temp.join("install/www")).unwrap());
    assert_eq!(chosen.source, "executable sidecar");
}

#[test]
fn s04_debug_repository_root_fallback() {
    let temp = TempDirectory::new();
    repository_markers(&temp.0);
    minimal_bundle(&temp.join("www"));
    let chosen = resolve(None, None, &temp.join("target/debug/examples/app.exe"), &temp.0, true).unwrap();
    assert_eq!(chosen.path, fs::canonicalize(temp.join("www")).unwrap());
    assert_eq!(chosen.source, "debug repository fallback");
}

#[test]
fn s05_release_never_uses_repository_cwd_fallback() {
    let temp = TempDirectory::new();
    repository_markers(&temp.0);
    minimal_bundle(&temp.join("www"));
    let failed = error(resolve(None, None, &temp.join("install/app.exe"), &temp.0, false));
    assert_eq!(failed.kind(), io::ErrorKind::NotFound);
    assert!(failed.to_string().contains("restricted to debug"));
}

#[test]
fn s06_invalid_builder_cannot_fall_back() {
    let temp = TempDirectory::new();
    minimal_bundle(&temp.join("www"));
    fs::write(temp.join("file"), b"ordinary file").unwrap();
    for name in ["missing", "file"] {
        let failed = error(resolve(Some(&temp.join(name)), Some(&temp.join("www")), &temp.join("app.exe"), &temp.0, true));
        assert!(failed.to_string().contains("(builder)"));
        assert!(failed.to_string().contains(name));
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        let _lock = fs::OpenOptions::new().read(true).share_mode(0).open(temp.join("www/index.html")).unwrap();
        assert!(resolve(Some(&temp.join("www")), None, &temp.join("app.exe"), &temp.0, true).is_err());
    }
}

#[test]
fn s07_invalid_environment_cannot_fall_back_to_sidecar() {
    let temp = TempDirectory::new();
    minimal_bundle(&temp.join("www"));
    let failed = error(resolve(None, Some(&temp.join("missing")), &temp.join("app.exe"), &temp.0, true));
    assert!(failed.to_string().contains("(STREAMLIT_STATIC_DIR)"));
}

#[test]
fn s08_empty_overrides_are_errors() {
    let temp = TempDirectory::new();
    minimal_bundle(&temp.join("www"));
    for (builder, environment) in [(Some(Path::new("")), None), (None, Some(Path::new("")))] {
        let failed = error(resolve(builder, environment, &temp.join("app.exe"), &temp.0, true));
        assert_eq!(failed.kind(), io::ErrorKind::InvalidInput);
        assert!(failed.to_string().contains("empty directory path"));
    }
}

#[test]
fn s09_missing_directory_or_unreadable_index_is_rejected() {
    let temp = TempDirectory::new();
    minimal_bundle(&temp.join("www"));
    let index = temp.join("www/index.html");
    fs::remove_file(&index).unwrap();
    assert!(resolve(Some(&temp.join("www")), None, &temp.join("app.exe"), &temp.0, true).is_err());
    fs::create_dir(&index).unwrap();
    assert!(resolve(Some(&temp.join("www")), None, &temp.join("app.exe"), &temp.0, true).is_err());
    fs::remove_dir(&index).unwrap();
    fs::write(&index, OFFICIAL_INDEX).unwrap();
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        let _lock = fs::OpenOptions::new().read(true).share_mode(0).open(&index).unwrap();
        assert!(resolve(Some(&temp.join("www")), None, &temp.join("app.exe"), &temp.0, true).is_err());
    }
}

#[test]
fn s10_invalid_existing_sidecar_prevents_debug_fallback() {
    let temp = TempDirectory::new();
    repository_markers(&temp.0);
    minimal_bundle(&temp.join("www"));
    minimal_bundle(&temp.join("install/www"));
    fs::write(temp.join("install/www/index.html"), b"old or unrelated index").unwrap();
    let failed = error(resolve(None, None, &temp.join("install/app.exe"), &temp.0, true));
    assert!(failed.to_string().contains("(executable sidecar)"));
    assert!(failed.to_string().contains("pinned official 1.66.1"));
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        fs::write(temp.join("install/www/index.html"), OFFICIAL_INDEX).unwrap();
        let _lock = fs::OpenOptions::new().read(true).share_mode(0).open(temp.join("install/www/index.html")).unwrap();
        assert!(resolve(None, None, &temp.join("install/app.exe"), &temp.0, true).is_err());
    }
}

#[test]
fn s11_missing_empty_or_unreadable_js_and_css_are_rejected() {
    let temp = TempDirectory::new();
    minimal_bundle(&temp.join("www"));
    fs::write(temp.join("outside.js"), b"outside the selected root").unwrap();
    assert!(checked_asset(&fs::canonicalize(temp.join("www")).unwrap(), "../outside.js").is_err());
    for suffix in [".js", ".css"] {
        let asset = temp.join("www").join(boot_assets().find(|name| name.ends_with(suffix)).unwrap());
        fs::remove_file(&asset).unwrap();
        assert!(resolve(Some(&temp.join("www")), None, &temp.join("app.exe"), &temp.0, true).is_err());
        fs::write(&asset, b"").unwrap();
        assert!(resolve(Some(&temp.join("www")), None, &temp.join("app.exe"), &temp.0, true).is_err());
        fs::write(&asset, b"availability fixture").unwrap();
        #[cfg(windows)]
        {
            use std::os::windows::fs::OpenOptionsExt;
            let _lock = fs::OpenOptions::new().read(true).share_mode(0).open(&asset).unwrap();
            assert!(resolve(Some(&temp.join("www")), None, &temp.join("app.exe"), &temp.0, true).is_err());
        }
    }
}

#[test]
fn s12_no_candidate_without_repository_markers_fails() {
    let temp = TempDirectory::new();
    minimal_bundle(&temp.join("www"));
    let failed = error(resolve(None, None, &temp.join("install/app.exe"), &temp.0, true));
    assert!(failed.to_string().contains("no static directory"));
    assert!(failed.to_string().contains("with_static_dir or STREAMLIT_STATIC_DIR"));
}

struct OwnedProcess(Child);

impl Drop for OwnedProcess {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn copy_tree(source: &Path, destination: &Path) -> usize {
    fs::create_dir_all(destination).unwrap();
    let mut count = 0;
    for item in fs::read_dir(source).unwrap() {
        let item = item.unwrap();
        if item.file_type().unwrap().is_dir() {
            count += copy_tree(&item.path(), &destination.join(item.file_name()));
        } else {
            assert!(item.file_type().unwrap().is_file());
            fs::copy(item.path(), destination.join(item.file_name())).unwrap();
            assert_eq!(fs::read(item.path()).unwrap(), fs::read(destination.join(item.file_name())).unwrap());
            count += 1;
        }
    }
    count
}

fn child(executable: &Path, cwd: &Path, port: u16, environment: Option<&Path>, builder: Option<&Path>, log: &Path) -> OwnedProcess {
    let output = fs::File::create(log).unwrap();
    let mut command = Command::new(executable);
    command
        .args(["--exact", "server::tests::static_assets::relocated_process_http_static_and_ws", "--nocapture"])
        .current_dir(cwd)
        .env("STREAMLIT_TEST_STATIC_PORT", port.to_string())
        .env_remove("STREAMLIT_STATIC_DIR")
        .env_remove("STREAMLIT_TEST_STATIC_BUILDER")
        .stdout(Stdio::from(output.try_clone().unwrap()))
        .stderr(Stdio::from(output));
    if let Some(path) = environment {
        command.env("STREAMLIT_STATIC_DIR", path);
    }
    if let Some(path) = builder {
        command.env("STREAMLIT_TEST_STATIC_BUILDER", path);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000);
    }
    OwnedProcess(command.spawn().unwrap())
}

fn unused_port() -> u16 {
    std::net::TcpListener::bind(("127.0.0.1", 0)).unwrap().local_addr().unwrap().port()
}

async fn get(port: u16, path: &str) -> Vec<u8> {
    tokio::time::timeout(Duration::from_secs(10), async {
        let mut stream = TcpStream::connect(("127.0.0.1", port)).await.unwrap();
        stream.write_all(format!("GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n").as_bytes()).await.unwrap();
        let mut response = Vec::new();
        stream.read_to_end(&mut response).await.unwrap();
        assert!(response.starts_with(b"HTTP/1.1 200"));
        response.split_at(response.windows(4).position(|w| w == b"\r\n\r\n").unwrap() + 4).1.to_vec()
    })
    .await
    .unwrap()
}

async fn ready(process: &mut OwnedProcess, port: u16, log: &Path) {
    for _ in 0..100 {
        assert!(process.0.try_wait().unwrap().is_none(), "{}", fs::read_to_string(log).unwrap());
        if TcpStream::connect(("127.0.0.1", port)).await.is_ok() {
            return;
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    panic!("server not ready: {}", fs::read_to_string(log).unwrap());
}

async fn failed_before_bind(mut process: OwnedProcess, port: u16, log: &Path) {
    let status = tokio::time::timeout(Duration::from_secs(5), async {
        loop {
            if let Some(status) = process.0.try_wait().unwrap() {
                break status;
            }
            assert!(TcpStream::connect(("127.0.0.1", port)).await.is_err(), "bad assets opened a listening socket");
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
    })
    .await
    .unwrap();
    assert!(!status.success());
    assert!(fs::read_to_string(log).unwrap().contains("static assets"));
    assert!(TcpStream::connect(("127.0.0.1", port)).await.is_err());
}

async fn assert_websocket(port: u16) {
    let mut socket = TcpStream::connect(("127.0.0.1", port)).await.unwrap();
    socket
        .write_all(
            b"GET /_stcore/stream HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, PLACEHOLDER_AUTH_TOKEN\r\n\r\n",
        )
        .await
        .unwrap();
    let mut headers = Vec::new();
    while !headers.ends_with(b"\r\n\r\n") {
        headers.push(socket.read_u8().await.unwrap());
    }
    assert!(headers.starts_with(b"HTTP/1.1 101"));
    let state = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
    };
    send_binary(&mut socket, &state.encode_to_vec()).await;
    let mut new_session = false;
    loop {
        match receive(&mut socket).await.r#type {
            Some(forward_msg::Type::NewSession(_)) => new_session = true,
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                break;
            }
            _ => {}
        }
    }
    assert!(new_session);
}

#[actix_web::test]
async fn relocated_process_http_static_and_ws() {
    // A filtered subprocess of this test executable hosts the actual start().
    // In a --release test run this also exercises the real release-only policy.
    if let Some(port) = std::env::var_os("STREAMLIT_TEST_STATIC_PORT") {
        let mut server = StreamlitServer::new(entry, "127.0.0.1".into(), port.to_str().unwrap().parse().unwrap());
        if let Some(path) = std::env::var_os("STREAMLIT_TEST_STATIC_BUILDER") {
            server = server.with_static_dir(path);
        }
        server.start().await.unwrap();
        return;
    }
    let temp = TempDirectory::new();
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../www");
    assert_eq!(copy_tree(&root, &temp.join("install/www")), 347);
    let executable = temp.join(if cfg!(windows) { "install/app.exe" } else { "install/app" });
    fs::copy(std::env::current_exe().unwrap(), &executable).unwrap();
    fs::create_dir_all(temp.join("cwd/www")).unwrap();
    fs::write(temp.join("cwd/www/index.html"), b"decoy wrong frontend").unwrap();
    let port = unused_port();
    let log = temp.join("sidecar.log");
    let mut process = child(&executable, &temp.join("cwd"), port, None, None, &log);
    ready(&mut process, port, &log).await;
    assert_eq!(get(port, "/").await, fs::read(root.join("index.html")).unwrap());
    for name in boot_assets() {
        assert_eq!(get(port, &format!("/{name}")).await, fs::read(root.join(name)).unwrap());
    }
    assert_eq!(get(port, "/_stcore/health").await, b"ok");
    assert_websocket(port).await;
    drop(process);

    // Absolute and relative explicit paths work from a different CWD, and a
    // valid builder remains usable even when the environment is invalid.
    for builder in [None, Some(root.as_path())] {
        let environment = if builder.is_some() { temp.join("missing") } else { PathBuf::from("../install/www") };
        let port = unused_port();
        let log = temp.join("override.log");
        let mut process = child(&executable, &temp.join("cwd"), port, Some(&environment), builder, &log);
        ready(&mut process, port, &log).await;
        assert_eq!(get(port, "/").await, OFFICIAL_INDEX.as_bytes());
        assert_websocket(port).await;
    }

    // Production startup must fail before bind even with a valid sidecar.
    for builder in [None, Some(temp.join("missing"))] {
        let port = unused_port();
        let log = temp.join("invalid.log");
        let process = child(&executable, &temp.join("cwd"), port, Some(&temp.join("missing")), builder.as_deref(), &log);
        failed_before_bind(process, port, &log).await;
    }

    // No sidecar: a decoy working directory may never become the frontend.
    fs::create_dir(temp.join("no-assets")).unwrap();
    let bare_executable = temp.join(if cfg!(windows) { "no-assets/app.exe" } else { "no-assets/app" });
    fs::copy(&executable, &bare_executable).unwrap();
    let port = unused_port();
    let log = temp.join("missing.log");
    failed_before_bind(child(&bare_executable, &temp.join("cwd"), port, None, None, &log), port, &log).await;

    // Exercise start()'s actual cfg!(debug_assertions), not just a resolver flag.
    let repository = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
    let port = unused_port();
    let log = temp.join("repository-cwd.log");
    let mut process = child(&bare_executable, repository, port, None, None, &log);
    if cfg!(debug_assertions) {
        ready(&mut process, port, &log).await;
        assert_eq!(get(port, "/").await, OFFICIAL_INDEX.as_bytes());
        assert_websocket(port).await;
    } else {
        failed_before_bind(process, port, &log).await;
    }
}
