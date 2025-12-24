#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{
    delta, delta_base_with_path, element, forward_msg, FileUploader as ProtoFileUploader, Delta,
};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

/// File uploader element
pub(crate) struct FileUploaderElement {
    label: String,
    key: Option<String>,
    type_filters: Vec<String>,
    accept_multiple_files: bool,
    help: Option<String>,
    disabled: bool,
    accept_directory: bool,
}

impl FileUploaderElement {
    pub fn new(label: String, key: Option<String>) -> Self {
        Self {
            label,
            key,
            type_filters: vec![],
            accept_multiple_files: false,
            help: None,
            disabled: false,
            accept_directory: false,
        }
    }

    pub fn type_filters(&mut self, filters: Vec<String>) {
        self.type_filters = filters;
    }

    pub fn accept_multiple_files(&mut self, accept: bool) {
        self.accept_multiple_files = accept;
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }

    pub fn accept_directory(&mut self, accept: bool) {
        self.accept_directory = accept;
    }

    pub fn key(&self) -> Option<&str> {
        self.key.as_deref()
    }
}

impl Element for FileUploaderElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(
            format!(
                "file_uploader_{}_{}",
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
                r#type: Some(element::Type::FileUploader(ProtoFileUploader {
                    id: self.key.clone().unwrap_or_default(),
                    label: self.label.clone(),
                    r#type: self.type_filters.clone(),
                    max_upload_size_mb: 200, // Default max size
                    multiple_files: self.accept_multiple_files,
                    help: self.help.clone().unwrap_or_default(),
                    form_id: String::new(),
                    disabled: self.disabled,
                    label_visibility: None,
                    accept_directory: self.accept_directory,
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

pub struct FileUploader {
    element: Arc<RefCell<FileUploaderElement>>,
}

impl FileUploader {
    pub(crate) fn new(element: Arc<RefCell<FileUploaderElement>>) -> Self {
        Self { element }
    }
}
