#pragma once

#include <Arduino.h>
#include "MotorDriver.h"

class MecanumJoystickMapper {
public:
    explicit MecanumJoystickMapper(uint8_t deadzone_percent);

    void set_deadzone_percent(uint8_t deadzone_percent);
    uint8_t deadzone_percent() const;

    void drive(
        MecanumCarDriver& car,
        int16_t axis_strafe,
        int16_t axis_forward,
        int16_t axis_spin,
        int16_t axis_pivot,
        uint8_t max_speed) const;

private:
    uint8_t _deadzone_percent;

    int16_t normalize_axis(int16_t axis) const;
};
