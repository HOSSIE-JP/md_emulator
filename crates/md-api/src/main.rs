use std::net::SocketAddr;
use std::sync::{Arc, Mutex};

use md_api::router;
use md_core::Emulator;

#[tokio::main]
async fn main() {
    println!("md-api startup: set MD_API_LOG=1 to enable API request logs");
    let emulator = Arc::new(Mutex::new(Emulator::new()));
    let app = router(emulator);

    let port: u16 = std::env::var("MD_API_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(8080);
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("failed to bind server address");

    axum::serve(listener, app)
        .await
        .expect("server exited with error");
}
