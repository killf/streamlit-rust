use crate::error::{Result, StreamlitError};
use base64::{engine::general_purpose::STANDARD, Engine as _};
use chrono::{DateTime, Utc};
use jsonwebtoken::{decode, encode, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthToken {
    pub sub: String,              // Subject (user ID)
    pub exp: usize,               // Expiration time
    pub iat: usize,               // Issued at
    pub jti: String,              // JWT ID
    pub session_id: String,       // Session ID
    pub permissions: Vec<String>, // User permissions
}

pub struct AuthManager {
    encoding_key: EncodingKey,
    decoding_key: DecodingKey,
    validation: Validation,
    token_duration: std::time::Duration,
}

impl AuthManager {
    pub fn new(secret: &str) -> Self {
        Self {
            encoding_key: EncodingKey::from_secret(secret.as_ref()),
            decoding_key: DecodingKey::from_secret(secret.as_ref()),
            validation: Validation::default(),
            token_duration: std::time::Duration::from_secs(3600), // 1 hour
        }
    }

    pub fn generate_token(
        &self,
        user_id: &str,
        session_id: &str,
        permissions: Vec<String>,
    ) -> Result<String> {
        let now = Utc::now();
        let exp = now + chrono::Duration::from_std(self.token_duration).unwrap();

        let claims = AuthToken {
            sub: user_id.to_string(),
            exp: exp.timestamp() as usize,
            iat: now.timestamp() as usize,
            jti: Uuid::new_v4().to_string(),
            session_id: session_id.to_string(),
            permissions,
        };

        let token = encode(&Header::default(), &claims, &self.encoding_key).map_err(|e| {
            StreamlitError::Authentication(format!("Failed to generate token: {}", e))
        })?;

        Ok(token)
    }

    pub fn validate_token(&self, token: &str) -> Result<AuthToken> {
        let token_data = decode::<AuthToken>(token, &self.decoding_key, &self.validation)
            .map_err(|e| StreamlitError::Authentication(format!("Invalid token: {}", e)))?;

        Ok(token_data.claims)
    }

    pub fn extract_session_id(&self, token: &str) -> Result<String> {
        let claims = self.validate_token(token)?;
        Ok(claims.session_id)
    }
}

pub struct BasicAuth {
    username: String,
    password: String,
}

impl BasicAuth {
    pub fn new(username: String, password: String) -> Self {
        Self { username, password }
    }

    pub fn validate(&self, auth_header: &str) -> bool {
        if let Some(encoded) = auth_header.strip_prefix("Basic ") {
            if let Ok(decoded) = STANDARD.decode(encoded) {
                if let Ok(creds) = String::from_utf8(decoded) {
                    if let Some((username, password)) = creds.split_once(':') {
                        return username == self.username && password == self.password;
                    }
                }
            }
        }
        false
    }

    pub fn generate_header(&self) -> String {
        let creds = format!("{}:{}", self.username, self.password);
        let encoded = STANDARD.encode(creds.as_bytes());
        format!("Basic {}", encoded)
    }
}

pub fn extract_auth_token_from_headers(
    headers: &actix_web::http::header::HeaderMap,
) -> Option<String> {
    // Check Authorization header
    if let Some(auth_header) = headers.get("Authorization") {
        if let Ok(auth_str) = auth_header.to_str() {
            if auth_str.starts_with("Bearer ") {
                return Some(auth_str.strip_prefix("Bearer ").unwrap().to_string());
            }
        }
    }

    // Check cookie
    if let Some(cookie_header) = headers.get("Cookie") {
        if let Ok(cookie_str) = cookie_header.to_str() {
            for cookie in cookie_str.split(';') {
                let cookie = cookie.trim();
                if cookie.starts_with("streamlit_auth_token=") {
                    return Some(
                        cookie
                            .strip_prefix("streamlit_auth_token=")
                            .unwrap()
                            .to_string(),
                    );
                }
            }
        }
    }

    None
}

pub fn generate_session_token() -> String {
    Uuid::new_v4().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_auth() {
        let auth = BasicAuth::new("user".to_string(), "pass".to_string());

        let header = auth.generate_header();
        assert!(auth.validate(&header));

        assert!(!auth.validate("Basic invalid"));
        assert!(!auth.validate("Invalid dXNlcjpwYXNz"));
    }

    #[test]
    fn test_auth_manager() {
        let secret = "test_secret_key_12345";
        let auth_manager = AuthManager::new(secret);

        let user_id = "test_user";
        let session_id = "test_session";
        let permissions = vec!["read".to_string(), "write".to_string()];

        let token = auth_manager
            .generate_token(user_id, session_id, permissions.clone())
            .unwrap();

        let claims = auth_manager.validate_token(&token).unwrap();
        assert_eq!(claims.sub, user_id);
        assert_eq!(claims.session_id, session_id);
        assert_eq!(claims.permissions, permissions);
    }

    #[test]
    fn test_session_token_generation() {
        let token1 = generate_session_token();
        let token2 = generate_session_token();

        assert_ne!(token1, token2);
        assert!(Uuid::parse_str(&token1).is_ok());
        assert!(Uuid::parse_str(&token2).is_ok());
    }
}
