use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamlitConfig {
    pub server: ServerConfig,
    pub script: ScriptConfig,
    pub logger: LoggerConfig,
    pub security: SecurityConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    pub host: String,
    pub port: u16,
    pub enable_cors: bool,
    pub max_connections: usize,
    pub websocket_timeout: u64, // seconds
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScriptConfig {
    pub default_script_path: String,
    pub auto_reload: bool,
    pub max_script_runtime: u64, // seconds
    pub allow_python_imports: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoggerConfig {
    pub level: String,
    pub file: Option<PathBuf>,
    pub max_file_size: Option<u64>, // bytes
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityConfig {
    pub enable_auth: bool,
    pub secret_key: Option<String>,
    pub session_timeout: u64, // seconds
    pub max_session_age: u64, // seconds
}

impl Default for StreamlitConfig {
    fn default() -> Self {
        Self {
            server: ServerConfig {
                host: "127.0.0.1".to_string(),
                port: 8502,
                enable_cors: true,
                max_connections: 100,
                websocket_timeout: 300,
            },
            script: ScriptConfig {
                default_script_path: "./example/hello/main.py".to_string(),
                auto_reload: true,
                max_script_runtime: 60,
                allow_python_imports: vec![
                    "streamlit".to_string(),
                    "pandas".to_string(),
                    "numpy".to_string(),
                ],
            },
            logger: LoggerConfig {
                level: "info".to_string(),
                file: None,
                max_file_size: Some(10 * 1024 * 1024), // 10MB
            },
            security: SecurityConfig {
                enable_auth: false,
                secret_key: None,
                session_timeout: 1800,  // 30 minutes
                max_session_age: 86400, // 24 hours
            },
        }
    }
}

impl StreamlitConfig {
    pub fn from_env() -> Result<Self, Box<dyn std::error::Error>> {
        // Try to load from environment variables
        let mut config = Self::default();

        if let Ok(host) = std::env::var("STREAMLIT_HOST") {
            config.server.host = host;
        }

        if let Ok(port) = std::env::var("STREAMLIT_PORT") {
            config.server.port = port.parse()?;
        }

        if let Ok(script_path) = std::env::var("STREAMLIT_SCRIPT_PATH") {
            config.script.default_script_path = script_path;
        }

        if let Ok(log_level) = std::env::var("STREAMLIT_LOG_LEVEL") {
            config.logger.level = log_level;
        }

        Ok(config)
    }

    pub fn from_file(path: &str) -> Result<Self, Box<dyn std::error::Error>> {
        let content = std::fs::read_to_string(path)?;
        let config: Self = toml::from_str(&content)?;
        Ok(config)
    }

    pub fn save_to_file(&self, path: &str) -> Result<(), Box<dyn std::error::Error>> {
        let content = toml::to_string_pretty(self)?;
        std::fs::write(path, content)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = StreamlitConfig::default();
        assert_eq!(config.server.host, "127.0.0.1");
        assert_eq!(config.server.port, 8502);
        assert_eq!(config.logger.level, "info");
    }

    #[test]
    fn test_config_from_env() {
        std::env::set_var("STREAMLIT_PORT", "8080");
        let config = StreamlitConfig::from_env().unwrap();
        assert_eq!(config.server.port, 8080);
        std::env::remove_var("STREAMLIT_PORT");
    }

    #[test]
    fn test_config_serialization() {
        let config = StreamlitConfig::default();
        let serialized = toml::to_string_pretty(&config).unwrap();
        let deserialized: StreamlitConfig = toml::from_str(&serialized).unwrap();
        assert_eq!(config.server.host, deserialized.server.host);
    }
}
