//! GPIO motor control: real on Linux (rppal), no-op elsewhere.

#[cfg(target_os = "linux")]
use std::sync::OnceLock;

#[cfg(target_os = "linux")]
static PINS: OnceLock<(u8, u8, u8, u8)> = OnceLock::new();

// ---- Linux: real GPIO via rppal ----

#[cfg(target_os = "linux")]
pub fn init(left_forward: u8, left_backward: u8, right_forward: u8, right_backward: u8) {
    let _ = PINS.set((left_forward, left_backward, right_forward, right_backward));
}

#[cfg(target_os = "linux")]
fn set_pins(lf: bool, lb: bool, rf: bool, rb: bool) {
    if let Some(&(lf_pin, lb_pin, rf_pin, rb_pin)) = PINS.get() {
        if let Ok(gpio) = rppal::gpio::Gpio::new() {
            let set = |pin: u8, high: bool| {
                if let Ok(out) = gpio.get(pin).and_then(|p| p.into_output()) {
                    if high {
                        out.set_high();
                    } else {
                        out.set_low();
                    }
                }
            };
            set(lf_pin, lf);
            set(lb_pin, lb);
            set(rf_pin, rf);
            set(rb_pin, rb);
        }
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
