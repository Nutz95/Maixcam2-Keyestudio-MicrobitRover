#include "CommandDispatcher.h"
#include "Protocol.h"

namespace {
void stop_command(MecanumCarDriver& car, uint8_t) {
    car.stop();
}

constexpr CommandAction kCommandActions[] = {
    {CMD_FORWARD, "forward", &MecanumCarDriver::move_forward},
    {CMD_BACKWARD, "backward", &MecanumCarDriver::move_backward},
    {CMD_STRAFE_LEFT, "strafe_left", &MecanumCarDriver::strafe_left},
    {CMD_STRAFE_RIGHT, "strafe_right", &MecanumCarDriver::strafe_right},
    {CMD_DIAG_FL, "diag_forward_left", &MecanumCarDriver::diag_forward_left},
    {CMD_DIAG_FR, "diag_forward_right", &MecanumCarDriver::diag_forward_right},
    {CMD_DIAG_BL, "diag_backward_left", &MecanumCarDriver::diag_backward_left},
    {CMD_DIAG_BR, "diag_backward_right", &MecanumCarDriver::diag_backward_right},
    {CMD_SPIN_LEFT, "spin_left", &MecanumCarDriver::spin_left},
    {CMD_SPIN_RIGHT, "spin_right", &MecanumCarDriver::spin_right},
    {CMD_PIVOT_RIGHT, "pivot_right", &MecanumCarDriver::pivot_right},
    {CMD_PIVOT_REAR, "pivot_rear", &MecanumCarDriver::pivot_rear},
};
}

CommandDispatcher::CommandDispatcher(MecanumCarDriver& car)
    : _car(car),
      _joystick_mapper(DEFAULT_JOYSTICK_DEADZONE_PERCENT) {
}

bool CommandDispatcher::execute(uint8_t command, uint8_t speed) {
    if (command == CMD_STOP || speed == 0) {
        stop_command(_car, speed);
        return command == CMD_STOP || speed == 0;
    }

    for (const CommandAction& action : kCommandActions) {
        if (action.command == command) {
            (_car.*(action.action))(speed);
            return true;
        }
    }

    return false;
}

void CommandDispatcher::execute_raw(uint8_t wheel_dirs, uint8_t speed) {
    _car.drive_raw(wheel_dirs, speed);
}

void CommandDispatcher::execute_joystick(int16_t axis_x, int16_t axis_y, uint8_t max_speed) {
    _joystick_mapper.drive(_car, axis_x, axis_y, max_speed);
}

const char* CommandDispatcher::command_name(uint8_t command) const {
    if (command == CMD_STOP) {
        return "stop";
    }
    if (command == CMD_RAW) {
        return "raw";
    }
    if (command == CMD_JOYSTICK) {
        return "joystick";
    }

    for (const CommandAction& action : kCommandActions) {
        if (action.command == command) {
            return action.name;
        }
    }

    return "unknown";
}
