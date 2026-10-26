//! st.navigation / st.Page / st.switch_page on the measured 1.66.1 wire:
//! st.navigation registers the pages and streams one `navigation` ForwardMsg
//! (the pages with their BLAKE2b/16 url-path hashes, the sidebar position
//! and the current page) at the call point; nav.run() executes the current
//! page's body under that page's own script hash; the browser addresses
//! reruns by page hash, and st.switch_page finishes the run early and the
//! server starts the next run on the target page without a browser request
//! (see .codex/compatibility.md, Multipage navigation, frozen 2026-10-26).
use blake2::digest::consts::U16;
use blake2::{Blake2b, Digest};

use crate::Streamlit;
use crate::error::StreamlitError;
use crate::proto::{AppPage, ForwardMsg, Navigation as NavigationProto, PageInfo, forward_msg, navigation};
use crate::session::RunControl;

/// The fast hasher that names every page, the reference's `calc_hash`:
/// BLAKE2b with a 16-byte digest over the page's url path.
pub fn page_hash(url_path: &str) -> String {
    let mut hasher = Blake2b::<U16>::new();
    hasher.update(url_path.as_bytes());
    format!("{:x}", hasher.finalize())
}

#[derive(Default)]
pub(crate) struct NavigationStore {
    /// The page hash the browser reported with this run's request.
    pub(crate) incoming_page_hash: Option<String>,
    /// The page st.switch_page picked for the server-started next run.
    pub(crate) switch_target: Option<String>,
    /// url path -> page hash of the pages the last st.navigation call
    /// registered, for switch_page validation.
    registered: Vec<(String, String)>,
    /// The page this run resolved to.
    pub(crate) current: Option<String>,
}

/// One page of a `st.navigation` app: a title, its URL identity and the
/// body closure. The url path is the page's identity on the wire (its hash
/// derives from it) and defaults to the sanitized title.
pub struct Page<'a> {
    title: String,
    icon: Option<String>,
    url_path: String,
    default: bool,
    hidden: bool,
    render: Box<dyn Fn(&Streamlit) + 'a>,
}

impl<'a> Page<'a> {
    /// One page running `render` as its body, titled `title` (the nav label
    /// and the markdown header the frontend shows).
    pub fn new(title: impl Into<String>, render: impl Fn(&Streamlit) + 'a) -> Self {
        let title = title.into();
        let url_path = sanitize_url_path(&title);
        Self {
            title,
            url_path,
            icon: None,
            default: false,
            hidden: false,
            render: Box::new(render),
        }
    }

    /// The nav icon, any form the reference accepts (for example
    /// `":material/home:"` or an emoji); omit it for a plain entry.
    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = Some(icon.into());
        self
    }

    /// The page's URL pathname and identity (its hash derives from it).
    /// The default page always serves at the app root regardless.
    pub fn url_path(mut self, url_path: impl Into<String>) -> Self {
        self.url_path = url_path.into();
        self
    }

    /// Mark this page as the one an unaddressed first load runs.
    pub fn default(mut self, default: bool) -> Self {
        self.default = default;
        self
    }

    /// Keep the page reachable by hash and switch_page but out of the nav.
    pub fn hidden(mut self, hidden: bool) -> Self {
        self.hidden = hidden;
        self
    }
}

/// The reference's `_sanitize_url_path`: lowercase, whitespace to
/// underscores, URL-unsafe characters removed, underscores trimmed and
/// collapsed -- the fallback identity of a page built from its title.
fn sanitize_url_path(title: &str) -> String {
    let mut path = String::with_capacity(title.len());
    for character in title.trim().to_lowercase().chars() {
        if character.is_whitespace() {
            path.push('_');
        } else if !matches!(character, '&' | '#' | '?' | '/' | '\\' | ':' | '*' | '"' | '<' | '>' | '|' | '\'') {
            path.push(character);
        }
    }
    let path = path.trim_matches('_');
    let mut collapsed = String::with_capacity(path.len());
    let mut previous_underscore = false;
    for character in path.chars() {
        let is_underscore = character == '_';
        if !(is_underscore && previous_underscore) {
            collapsed.push(character);
        }
        previous_underscore = is_underscore;
    }
    collapsed
}

/// The navigation handle `st.navigation` returns: call `run` to execute the
/// current page's body.
pub struct Navigation<'a> {
    st: &'a Streamlit,
    pages: Vec<Page<'a>>,
    current: String,
}

impl Navigation<'_> {
    /// Run the current page's body under its own script hash, like the
    /// reference's `pg.run()`. A run that already switched or stopped does
    /// nothing here.
    pub fn run(&self) {
        if self.st.session_state().run_control().is_some() {
            return;
        }
        let Some(page) = self.pages.iter().find(|page| page_hash(&page.url_path) == self.current) else {
            return;
        };
        let previous_hash = {
            let mut app = self.st.app.lock();
            app.render_context_mut().map(|context| std::mem::replace(&mut context.active_script_hash, self.current.clone()))
        };
        (page.render)(self.st);
        if let Some(previous) = previous_hash
            && let Some(context) = self.st.app.lock().render_context_mut()
        {
            context.active_script_hash = previous;
        }
    }
}

fn emit_navigation(st: &Streamlit, pages: &[Page<'_>], current: &str) {
    let mut app = st.app.lock();
    if app.session_state.run_control().is_some() {
        return;
    }
    if let Some(context) = app.render_context_mut()
        && context.sender.is_some()
    {
        let app_pages = pages
            .iter()
            .map(|page| AppPage {
                page_script_hash: page_hash(&page.url_path),
                page_name: page.title.clone(),
                icon: page.icon.clone().unwrap_or_default(),
                is_default: page.default,
                section_header: String::new(),
                url_pathname: if page.default { String::new() } else { page.url_path.clone() },
                is_hidden: page.hidden,
                external_url: None,
            })
            .collect::<Vec<_>>();
        let mut message = ForwardMsg {
            hash: "navigation".to_string(),
            ..Default::default()
        };
        message.r#type = Some(forward_msg::Type::Navigation(NavigationProto {
            sections: vec![String::new()],
            app_pages,
            position: navigation::Position::Sidebar as i32,
            page_script_hash: current.to_string(),
            expanded: false,
            visible_items: None,
        }));
        context.push(message);
    }
}

impl Streamlit {
    /// Register the app's pages and stream the nav, like `st.navigation`:
    /// `st.navigation([Page::new("Main", render_main).default(true),
    /// Page::new("Two", render_two)]).run()`. The current page is the one
    /// the browser addressed by hash, or the default page.
    pub fn navigation<'a>(&'a self, pages: impl IntoIterator<Item = Page<'a>>) -> Navigation<'a> {
        let pages: Vec<_> = pages.into_iter().collect();
        let state = self.session_state();
        let current = {
            let mut store = state.navigation.lock();
            let current = store
                .incoming_page_hash
                .as_ref()
                .filter(|incoming| pages.iter().any(|page| page_hash(&page.url_path) == **incoming))
                .cloned()
                .or_else(|| pages.iter().find(|page| page.default).or_else(|| pages.first()).map(|page| page_hash(&page.url_path)))
                .unwrap_or_default();
            store.registered = pages.iter().map(|page| (page.url_path.clone(), page_hash(&page.url_path))).collect();
            store.current = Some(current.clone());
            current
        };
        emit_navigation(self, &pages, &current);
        Navigation { st: self, pages, current }
    }

    /// Switch to another registered page, like `st.switch_page`: the current
    /// run finishes `FINISHED_EARLY_FOR_RERUN` after streaming the empty
    /// query string, and the server starts the next run on the target page
    /// without a browser request. The target is the page's url path.
    pub fn switch_page(&self, url_path: &str) -> Result<(), StreamlitError> {
        let state = self.session_state();
        if state.run_control().is_some() {
            return Ok(());
        }
        let target = {
            let store = state.navigation.lock();
            store
                .registered
                .iter()
                .find(|(registered, _)| registered == url_path)
                .map(|(_, hash)| hash.clone())
                .ok_or_else(|| StreamlitError::Session(format!("st.switch_page: no registered page with url path '{url_path}'")))?
        };
        {
            let mut app = self.app.lock();
            if let Some(context) = app.render_context_mut()
                && context.sender.is_some()
            {
                let mut message = ForwardMsg {
                    hash: "page_info_changed".to_string(),
                    ..Default::default()
                };
                message.r#type = Some(forward_msg::Type::PageInfoChanged(PageInfo { query_string: String::new() }));
                context.push(message);
            }
        }
        state.navigation.lock().switch_target = Some(target);
        state.set_run_control(RunControl::Rerun);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn page_hashes_follow_the_measured_formula() {
        assert_eq!(page_hash("render_main"), "4e89e30dce2a0c9070887e292d3255e7");
        assert_eq!(page_hash("two"), "d681734f8c454b90df4d5feea7487445");
    }

    #[test]
    fn url_paths_sanitize_like_the_reference() {
        assert_eq!(sanitize_url_path("My  Two__Pages"), "my_two_pages");
        assert_eq!(sanitize_url_path(" A&B / C? "), "ab_c");
    }
}
