use actix_web::{get, web, App, Error, HttpRequest, HttpResponse, HttpServer, Responder};
use actix_ws::AggregatedMessage;
use futures_util::StreamExt as _;

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

        async fn echo(req: HttpRequest, stream: web::Payload) -> Result<HttpResponse, Error> {
            let (res, mut session, stream) = actix_ws::handle(&req, stream)?;

            let mut stream = stream
                .aggregate_continuations()
                .max_continuation_size(2_usize.pow(20));

            actix_web::rt::spawn(async move {
                while let Some(msg) = stream.next().await {
                    match msg {
                        Ok(AggregatedMessage::Text(text)) => {
                            session.text(text).await.unwrap();
                        }

                        Ok(AggregatedMessage::Binary(bin)) => {
                            session.binary(bin).await.unwrap();
                        }

                        Ok(AggregatedMessage::Ping(msg)) => {
                            session.pong(&msg).await.unwrap();
                        }

                        _ => {}
                    }
                }
            });

            Ok(res)
        }

        actix_web::rt::System::new().block_on(async move {
            HttpServer::new(|| App::new().service(index).route("/", web::get().to(echo)))
                .bind(("127.0.0.1", 8080))?
                .run()
                .await
        })
    }
}
