//! GPIO motor control: real on Linux (rppal), no-op elsewhere.
//! Output pins are initialized once and reused to avoid per-command overhead.

#[cfg(target_os = "linux")]
use std::sync::atomic::{AtomicU8, Ordering};

#[cfg(target_os = "linux")]
use std::sync::OnceLock;

// Cached output pins: (left_forward, left_backward, right_forward, right_backward).
// Initialized once in init(); set_pins() only calls set_high/set_low.
#[cfg(target_os = "linux")]
static OUTPUTS: OnceLock<(
    rppal::gpio::OutputPin,
    rppal::gpio::OutputPin,
    rppal::gpio::OutputPin,
    rppal::gpio::OutputPin,
)> = OnceLock::new();

// Packed last pin state (lf, lb, rf, rb) as nibbles to skip no-op writes.
#[cfg(target_os = "linux")]
static LAST_STATE: AtomicU8 = AtomicU8::new(0xFF); // invalid so first write always runs

#[cfg(target_os = "linux")]
fn pack_state(lf: bool, lb: bool, rf: bool, rb: bool) -> u8 {
    (lf as u8) | ((lb as u8) << 1) | ((rf as u8) << 2) | ((rb as u8) << 3)
}

#[cfg(target_os = "linux")]
pub fn init(left_forward: u8, left_backward: u8, right_forward: u8, right_backward: u8) {
    let gpio = match rppal::gpio::Gpio::new() {
        Ok(g) => g,
        Err(e) => {
            eprintln!("GPIO init error: {}", e);
            return;
        }
    };
    let lf = match gpio.get(left_forward).map(|p| p.into_output()) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("GPIO pin {} error: {}", left_forward, e);
            return;
        }
    };
    let lb = match gpio.get(left_backward).map(|p| p.into_output()) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("GPIO pin {} error: {}", left_backward, e);
            return;
        }
    };
    let rf = match gpio.get(right_forward).map(|p| p.into_output()) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("GPIO pin {} error: {}", right_forward, e);
            return;
        }
    };
    let rb = match gpio.get(right_backward).map(|p| p.into_output()) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("GPIO pin {} error: {}", right_backward, e);
            return;
        }
    };
    if OUTPUTS.set((lf, lb, rf, rb)).is_err() {
        eprintln!("Motor outputs already initialized");
    }
}

#[cfg(target_os = "linux")]
fn set_pins(lf: bool, lb: bool, rf: bool, rb: bool) {
    let state = pack_state(lf, lb, rf, rb);
    if LAST_STATE.load(Ordering::Relaxed) == state {
        return;
    }
    LAST_STATE.store(state, Ordering::Relaxed);

    if let Some((ref lf_pin, ref lb_pin, ref rf_pin, ref rb_pin)) = OUTPUTS.get() {
        if lf {
            let _ = lf_pin.set_high();
        } else {
            let _ = lf_pin.set_low();
        }
        if lb {
            let _ = lb_pin.set_high();
        } else {
            let _ = lb_pin.set_low();
        }
        if rf {
            let _ = rf_pin.set_high();
        } else {
            let _ = rf_pin.set_low();
        }
        if rb {
            let _ = rb_pin.set_high();
        } else {
            let _ = rb_pin.set_low();
        }
    } else {
        eprintln!("Motor pins not initialized; call init() first");
    }
}

#[cfg(target_os = "linux")]
pub fn move_forward() {
    set_pins(true, false, true, false);
}

#[cfg(target_os = "linux")]
pub fn move_backward() {
    set_pins(false, true, false, true);
}

#[cfg(target_os = "linux")]
pub fn turn_left() {
    set_pins(false, true, true, false);
}

#[cfg(target_os = "linux")]
pub fn turn_right() {
    set_pins(true, false, false, true);
}

#[cfg(target_os = "linux")]
pub fn stop() {
    set_pins(false, false, false, false);
}

// ---- Non-Linux: no-ops ----

#[cfg(not(target_os = "linux"))]
pub fn init(_left_forward: u8, _left_backward: u8, _right_forward: u8, _right_backward: u8) {}

#[cfg(not(target_os = "linux"))]
pub fn move_forward() {}

#[cfg(not(target_os = "linux"))]
pub fn move_backward() {}

#[cfg(not(target_os = "linux"))]
pub fn turn_left() {}

#[cfg(not(target_os = "linux"))]
pub fn turn_right() {}

#[cfg(not(target_os = "linux"))]
pub fn stop() {}
