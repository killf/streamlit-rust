pub enum ElementWidth {
    Stretch,
    Content,
    Value(i32),
}

pub enum TextAlignment {
    Left,
    Center,
    Right,
    Justify,
}

pub trait Renderable {
    fn render(&self) -> String;
}