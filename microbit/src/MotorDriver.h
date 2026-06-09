#pragma once

#include <Arduino.h>
#include <Wire.h>

class MecanumCarDriver {
public:
    MecanumCarDriver();

    void begin();
    void set_pwm(uint8_t channel, uint8_t value);
    void set_all_pwm(uint8_t value);

    void motor_upper_left(uint8_t forward, uint8_t speed);
    void motor_lower_left(uint8_t forward, uint8_t speed);
    void motor_upper_right(uint8_t forward, uint8_t speed);
    void motor_lower_right(uint8_t forward, uint8_t speed);

    void stop();
    // Registres 0x09/0x0A : LEDs RGB sous le chassis (pas les LEDs avant)
    void set_under_rgb_leds(bool on);

    void move_forward(uint8_t speed);
    void move_backward(uint8_t speed);
    void strafe_left(uint8_t speed);
    void strafe_right(uint8_t speed);
    void diag_forward_left(uint8_t speed);
    void diag_forward_right(uint8_t speed);
    void diag_backward_left(uint8_t speed);
    void diag_backward_right(uint8_t speed);
    void spin_left(uint8_t speed);
    void spin_right(uint8_t speed);
    void pivot_right(uint8_t speed);
    void pivot_rear(uint8_t speed);
    void drive_raw(uint8_t wheel_dirs, uint8_t speed);

private:
    static const uint8_t I2C_ADDRESS = 0x30;
    static const uint8_t LED_LEFT_REG = 0x09;
    static const uint8_t LED_RIGHT_REG = 0x0A;
};
