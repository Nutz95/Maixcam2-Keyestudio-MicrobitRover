#include "MotorDriver.h"
#include "Protocol.h"

MecanumCarDriver::MecanumCarDriver() {
}

void MecanumCarDriver::begin() {
    Wire.begin();
    set_all_pwm(0);
    delay(5);
}

void MecanumCarDriver::set_pwm(uint8_t channel, uint8_t value) {
    Wire.beginTransmission(I2C_ADDRESS);
    Wire.write(channel);
    Wire.write(value & 0xFF);
    Wire.endTransmission();
}

void MecanumCarDriver::set_all_pwm(uint8_t value) {
    for (uint8_t i = 1; i <= 8; i++) {
        set_pwm(i, value);
    }
}

void MecanumCarDriver::motor_upper_left(uint8_t forward, uint8_t speed) {
    if (forward) {
        set_pwm(3, 0);
        set_pwm(4, speed);
    } else {
        set_pwm(3, speed);
        set_pwm(4, 0);
    }
}

void MecanumCarDriver::motor_lower_left(uint8_t forward, uint8_t speed) {
    if (forward) {
        set_pwm(7, 0);
        set_pwm(8, speed);
    } else {
        set_pwm(7, speed);
        set_pwm(8, 0);
    }
}

void MecanumCarDriver::motor_upper_right(uint8_t forward, uint8_t speed) {
    if (forward) {
        set_pwm(1, 0);
        set_pwm(2, speed);
    } else {
        set_pwm(1, speed);
        set_pwm(2, 0);
    }
}

void MecanumCarDriver::motor_lower_right(uint8_t forward, uint8_t speed) {
    if (forward) {
        set_pwm(5, 0);
        set_pwm(6, speed);
    } else {
        set_pwm(5, speed);
        set_pwm(6, 0);
    }
}

void MecanumCarDriver::stop() {
    set_all_pwm(0);
}

void MecanumCarDriver::set_under_rgb_leds(bool on) {
    uint8_t value = on ? 1 : 0;
    set_pwm(LED_LEFT_REG, value);
    set_pwm(LED_RIGHT_REG, value);
}

void MecanumCarDriver::move_forward(uint8_t speed) {
    motor_upper_left(1, speed);
    motor_lower_left(1, speed);
    motor_upper_right(1, speed);
    motor_lower_right(1, speed);
}

void MecanumCarDriver::move_backward(uint8_t speed) {
    motor_upper_left(0, speed);
    motor_lower_left(0, speed);
    motor_upper_right(0, speed);
    motor_lower_right(0, speed);
}

void MecanumCarDriver::strafe_left(uint8_t speed) {
    motor_upper_left(0, speed);
    motor_lower_left(1, speed);
    motor_upper_right(1, speed);
    motor_lower_right(0, speed);
}

void MecanumCarDriver::strafe_right(uint8_t speed) {
    motor_upper_left(1, speed);
    motor_lower_left(0, speed);
    motor_upper_right(0, speed);
    motor_lower_right(1, speed);
}

void MecanumCarDriver::diag_forward_left(uint8_t speed) {
    motor_upper_left(1, 0);
    motor_lower_left(1, speed);
    motor_upper_right(1, speed);
    motor_lower_right(1, 0);
}

void MecanumCarDriver::diag_forward_right(uint8_t speed) {
    motor_upper_left(1, speed);
    motor_lower_left(1, 0);
    motor_upper_right(1, 0);
    motor_lower_right(1, speed);
}

void MecanumCarDriver::diag_backward_left(uint8_t speed) {
    motor_upper_left(0, speed);
    motor_lower_left(0, 0);
    motor_upper_right(0, 0);
    motor_lower_right(0, speed);
}

void MecanumCarDriver::diag_backward_right(uint8_t speed) {
    motor_upper_left(0, 0);
    motor_lower_left(0, speed);
    motor_upper_right(0, speed);
    motor_lower_right(0, 0);
}

void MecanumCarDriver::spin_left(uint8_t speed) {
    motor_upper_left(0, speed);
    motor_lower_left(0, speed);
    motor_upper_right(1, speed);
    motor_lower_right(1, speed);
}

void MecanumCarDriver::spin_right(uint8_t speed) {
    motor_upper_left(1, speed);
    motor_lower_left(1, speed);
    motor_upper_right(0, speed);
    motor_lower_right(0, speed);
}

void MecanumCarDriver::pivot_right(uint8_t speed) {
    motor_upper_left(1, speed);
    motor_lower_left(1, speed);
    motor_upper_right(1, 0);
    motor_lower_right(1, 0);
}

void MecanumCarDriver::pivot_rear(uint8_t speed) {
    motor_upper_left(1, speed);
    motor_upper_right(0, speed);
    motor_lower_left(1, 0);
    motor_lower_right(1, 0);
}

void MecanumCarDriver::drive_raw(uint8_t wheel_dirs, uint8_t speed) {
    const uint8_t dirs[4] = {
        wheel_dir_bits(wheel_dirs, 0),
        wheel_dir_bits(wheel_dirs, 2),
        wheel_dir_bits(wheel_dirs, 4),
        wheel_dir_bits(wheel_dirs, 6),
    };

    void (MecanumCarDriver::*motors[4])(uint8_t, uint8_t) = {
        &MecanumCarDriver::motor_upper_left,
        &MecanumCarDriver::motor_upper_right,
        &MecanumCarDriver::motor_lower_left,
        &MecanumCarDriver::motor_lower_right,
    };

    for (uint8_t i = 0; i < 4; i++) {
        switch (dirs[i]) {
            case WHEEL_DIR_FORWARD:
                (this->*motors[i])(1, speed);
                break;
            case WHEEL_DIR_BACKWARD:
                (this->*motors[i])(0, speed);
                break;
            default:
                (this->*motors[i])(1, 0);
                break;
        }
    }
}
