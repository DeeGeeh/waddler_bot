//! PyO3 module exposing motor commands to Python.
//! WebSocket server calls execute_command(cmd) with forward|backward|left|right|stop.

use pyo3::prelude::*;

mod motor;

/// Dispatch joystick command string to motor layer.
/// Called directly by the movement pipeline (no AI).
#[pyfunction]
fn execute_command(cmd: &str) {
    match cmd.trim().to_lowercase().as_str() {
        "forward" => motor::move_forward(),
        "backward" => motor::move_backward(),
        "left" => motor::turn_left(),
        "right" => motor::turn_right(),
        "stop" | _ => motor::stop(),
    }
}

#[pymodule]
fn rust_motor(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(execute_command, m)?)?;
    Ok(())
}
