use std::time::Duration;
use ::streamlit::*;
use tokio::time::sleep;

#[main]
async fn main(st: &Streamlit) {
    for i in 0..10 {
        st.write(format!("Count {}\n", i));
        sleep(Duration::from_secs(1)).await;
    }
}
