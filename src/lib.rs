use actix_web::{get, App, HttpServer, Responder};

pub struct Streamlit;

impl Streamlit {
    pub fn write(&self, value: &str) {
        println!("{}", value);
    }

    pub fn run(&self) -> std::io::Result<()> {
        #[get("/")]
        async fn index() -> impl Responder {
            "Hello world!"
        }

        actix_web::rt::System::new().block_on(async move {
            HttpServer::new(|| App::new().service(index))
                .bind(("127.0.0.1", 8080))?
                .run()
                .await
        })
    }
}
