use std::alloc::{alloc, dealloc, Layout};
use std::cell::RefCell;

pub(crate) struct Allocator {
    object_list: RefCell<Vec<(*mut u8, Layout)>>,
}

impl Allocator {
    pub fn new() -> Self {
        Self { object_list: RefCell::new(vec![]) }
    }

    pub fn malloc<T>(&self, data: T) -> &mut T {
        let layout = Layout::new::<T>();
        unsafe {
            let ptr = alloc(layout) as *mut T;
            std::ptr::write(ptr, data);
            self.object_list.borrow_mut().push((ptr as *mut u8, layout));
            &mut *ptr
        }
    }
}

impl Drop for Allocator {
    fn drop(&mut self) {
        for (ptr, layout) in self.object_list.borrow_mut().drain(..) {
            unsafe {
                dealloc(ptr, layout);
            }
        }
    }
}
