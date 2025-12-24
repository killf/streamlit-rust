use crate::core::AppendChild;

pub enum DividerConfig {
    Stretch,
    Value(i32),
}

impl From<&str> for DividerConfig {
    fn from(_: &str) -> Self {
        Self::Stretch
    }
}

impl From<i32> for DividerConfig {
    fn from(v: i32) -> Self {
        Self::Value(v)
    }
}

pub trait Divider {
    fn divider(&self) {
        self.divider_option(DividerConfig::Stretch);
    }
    fn divider_option<T: Into<DividerConfig>>(&self, option: T);
}

impl<C: AppendChild> Divider for C {
    fn divider_option<T: Into<DividerConfig>>(&self, option: T) {}
}
