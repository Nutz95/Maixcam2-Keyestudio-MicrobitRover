#pragma once

#include <Arduino.h>
#include "MotorDriver.h"

typedef void (MecanumCarDriver::*MotorCommandFn)(uint8_t speed);

struct CommandAction {
    uint8_t command;
    const char* name;
    MotorCommandFn action;
};
