#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{
    delta, delta_base_with_path, element, forward_msg, DownloadButton as ProtoDownloadButton, Delta,
};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

/// Download button element
pub(crate) struct DownloadButtonElement {
    label: String,
    key: Option<String>,
    data: Vec<u8>,
    file_name: String,
    mime_type: String,
    help: Option<String>,
    disabled: bool,
    use_container_width: bool,
}

impl DownloadButtonElement {
    pub fn new(label: String, key: Option<String>) -> Self {
        Self {
            label,
            key,
            data: vec![],
            file_name: "download".to_string(),
            mime_type: "application/octet-stream".to_string(),
            help: None,
            disabled: false,
            use_container_width: false,
        }
    }

    pub fn data(&mut self, data: Vec<u8>) {
        self.data = data;
    }

    pub fn file_name(&mut self, file_name: String) {
        self.file_name = file_name;
    }

    pub fn mime_type(&mut self, mime_type: String) {
        self.mime_type = mime_type;
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }

    pub fn use_container_width(&mut self, use_container_width: bool) {
        self.use_container_width = use_container_width;
    }

    pub fn key(&self) -> Option<&str> {
        self.key.as_deref()
    }

    /// Get the data URL for the download
    /// In production, this would be handled by the server
    pub fn get_url(&self) -> String {
        // For now, return a placeholder URL
        // In production, this would generate a proper data URL or server endpoint
        format!(
            "data:{};base64,{}",
            self.mime_type,
            base64_encode(&self.data)
        )
    }
}

fn base64_encode(data: &[u8]) -> String {
    use base64::prelude::*;
    BASE64_STANDARD.encode(data)
}

impl Element for DownloadButtonElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(
            format!(
                "download_button_{}_{}",
                self.label,
                self.key.clone().unwrap_or_default()
            )
            .as_str(),
        );
        let mut msg = delta_base_with_path(
            context.delta_path.clone(),
            context.active_script_hash.clone(),
            element_hash,
        );

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::DownloadButton(ProtoDownloadButton {
                    id: self.key.clone().unwrap_or_default(),
                    label: self.label.clone(),
                    r#default: false,
                    help: self.help.clone().unwrap_or_default(),
                    form_id: String::new(),
                    url: self.get_url(),
                    disabled: self.disabled,
                    use_container_width: self.use_container_width,
                    r#type: "primary".to_string(),
                    icon: String::new(),
                    ignore_rerun: false,
                    deferred_file_id: None,
                    shortcut: String::new(),
                    icon_position: 0,
                })),
            })),
        }));

        context.push(msg);

        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }

        Ok(())
    }
}

pub struct DownloadButton {
    element: Arc<RefCell<DownloadButtonElement>>,
}

impl DownloadButton {
    pub(crate) fn new(element: Arc<RefCell<DownloadButtonElement>>) -> Self {
        Self { element }
    }
}
