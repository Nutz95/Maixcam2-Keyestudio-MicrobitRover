#include "MecanumJoystickMapper.h"

#include <stdlib.h>

namespace {
constexpr int32_t kAxisMax = 32768;

int16_t clamp_signed_speed(int32_t value) {
    if (value > 255) {
        return 255;
    }
    if (value < -255) {
        return -255;
    }
    return static_cast<int16_t>(value);
}

int32_t min_i32(int32_t left, int32_t right) {
    return left < right ? left : right;
}

int32_t max_i32(int32_t left, int32_t right) {
    return left > right ? left : right;
}
}

MecanumJoystickMapper::MecanumJoystickMapper(uint8_t deadzone_percent)
    : _deadzone_percent(deadzone_percent) {
    set_deadzone_percent(deadzone_percent);
}

void MecanumJoystickMapper::set_deadzone_percent(uint8_t deadzone_percent) {
    _deadzone_percent = deadzone_percent > 95 ? 95 : deadzone_percent;
}

uint8_t MecanumJoystickMapper::deadzone_percent() const {
    return _deadzone_percent;
}

void MecanumJoystickMapper::drive(
    MecanumCarDriver& car,
    int16_t axis_x,
    int16_t axis_y,
    int16_t axis_rot,
    uint8_t max_speed) const {
    const int16_t x = normalize_axis(axis_x);
    const int16_t y = normalize_axis(static_cast<int16_t>(-axis_y));
    const int16_t r = normalize_axis(axis_rot);

    if (x == 0 && y == 0 && r == 0) {
        car.stop();
        return;
    }

    const int32_t upper_left = static_cast<int32_t>(y) + x + r;
    const int32_t upper_right = static_cast<int32_t>(y) - x - r;
    const int32_t lower_left = static_cast<int32_t>(y) - x + r;
    const int32_t lower_right = static_cast<int32_t>(y) + x - r;

    int32_t max_magnitude = labs(upper_left);
    max_magnitude = max_i32(max_magnitude, labs(upper_right));
    max_magnitude = max_i32(max_magnitude, labs(lower_left));
    max_magnitude = max_i32(max_magnitude, labs(lower_right));
    if (max_magnitude == 0) {
        car.stop();
        return;
    }

    int32_t input_mag = max_i32(max_i32(labs(x), labs(y)), labs(r));
    int32_t effective = (static_cast<int32_t>(max_speed) * input_mag) / kAxisMax;

    car.drive_signed(
        clamp_signed_speed((upper_left * effective) / max_magnitude),
        clamp_signed_speed((upper_right * effective) / max_magnitude),
        clamp_signed_speed((lower_left * effective) / max_magnitude),
        clamp_signed_speed((lower_right * effective) / max_magnitude));
}

int16_t MecanumJoystickMapper::normalize_axis(int16_t axis) const {
    const int32_t deadzone = (kAxisMax * _deadzone_percent) / 100;
    const int32_t magnitude = labs(axis);
    if (magnitude <= deadzone) {
        return 0;
    }

    const int32_t scaled = ((magnitude - deadzone) * kAxisMax) / (kAxisMax - deadzone);
    const int32_t signed_scaled = axis < 0 ? -scaled : scaled;
    return static_cast<int16_t>(max_i32(-32768, min_i32(32767, signed_scaled)));
}
