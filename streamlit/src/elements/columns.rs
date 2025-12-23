// pub enum ColumnsOption {
//     Count(usize),
//     Weights(Vec<f32>),
// }
//
// impl From<usize> for ColumnsOption {
//     fn from(count: usize) -> Self {
//         ColumnsOption::Count(count)
//     }
// }
//
// impl From<i32> for ColumnsOption {
//     fn from(count: i32) -> Self {
//         ColumnsOption::Count(count as usize)
//     }
// }
//
// #[derive(Clone, PartialEq)]
// pub struct Column {
//     data: i32,
// }
//
// impl Column {
//     pub fn new(data: i32) -> Self {
//         Self { data }
//     }
// }
