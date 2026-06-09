#pragma once

#include <Arduino.h>
#include "CommandAction.h"
#include "MecanumJoystickMapper.h"
#include "MotorDriver.h"

class CommandDispatcher {
public:
    explicit CommandDispatcher(MecanumCarDriver& car);

    bool execute(uint8_t command, uint8_t speed);
    void execute_raw(uint8_t wheel_dirs, uint8_t speed);
    void execute_joystick(int16_t axis_x, int16_t axis_y, uint8_t max_speed);
    const char* command_name(uint8_t command) const;

private:
    MecanumCarDriver& _car;
    MecanumJoystickMapper _joystick_mapper;
};
