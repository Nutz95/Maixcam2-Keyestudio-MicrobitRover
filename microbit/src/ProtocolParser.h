#pragma once

#include <Arduino.h>
#include <Stream.h>
#include "Protocol.h"
#include "MotorDriver.h"
#include "SerialSafe.h"

enum RxState {
    WAIT_SYNC,
    WAIT_CMD,
    WAIT_SPEED_OR_DIRS,
    WAIT_RAW_SPEED,
    WAIT_CHECKSUM,
    WAIT_RAW_CHECKSUM,
};

struct RxContext {
    RxState state = WAIT_SYNC;
    uint8_t cmd = 0;
    uint8_t speed = 0;
    uint8_t dirs = 0;
};

class ProtocolHandler {
public:
    explicit ProtocolHandler(MecanumCarDriver& car) : _car(car) {}

    void feed(RxContext& ctx, uint8_t byte, Stream& reply_port, const char* src = "?") {
        switch (ctx.state) {
            case WAIT_SYNC:
                if (byte == PROTO_SYNC) {
                    ctx.state = WAIT_CMD;
                }
                break;

            case WAIT_CMD:
                ctx.cmd = byte;
                ctx.state = WAIT_SPEED_OR_DIRS;
                break;

            case WAIT_SPEED_OR_DIRS:
                if (ctx.cmd == CMD_RAW) {
                    ctx.dirs = byte;
                    ctx.state = WAIT_RAW_SPEED;
                } else {
                    ctx.speed = byte;
                    ctx.state = WAIT_CHECKSUM;
                }
                break;

            case WAIT_RAW_SPEED:
                ctx.speed = byte;
                ctx.state = WAIT_RAW_CHECKSUM;
                break;

            case WAIT_CHECKSUM:
                if (byte == proto_checksum(PROTO_SYNC, ctx.cmd, ctx.speed)) {
                    execute_command(ctx.cmd, ctx.speed, reply_port, src);
                }
                ctx.state = WAIT_SYNC;
                break;

            case WAIT_RAW_CHECKSUM:
                if (byte == proto_checksum4(PROTO_SYNC, CMD_RAW, ctx.dirs, ctx.speed)) {
                    _car.drive_raw(ctx.dirs, ctx.speed);
                    send_ack(reply_port, CMD_RAW);
                    log_command(CMD_RAW, ctx.speed, src);
                }
                ctx.state = WAIT_SYNC;
                break;
        }
    }

private:
    MecanumCarDriver& _car;

    void send_ack(Stream& port, uint8_t cmd) {
        stream_write_byte(port, PROTO_ACK);
        stream_write_byte(port, cmd);
    }

    void log_command(uint8_t cmd, uint8_t speed, const char* src) {
        char line[48];
        snprintf(line, sizeof(line), "[rover] %s cmd=0x%02X spd=%u", src, cmd, speed);
        serial_usb_println(line);
    }

    void execute_command(uint8_t cmd, uint8_t speed, Stream& reply_port, const char* src) {
        if (speed == 0 && cmd != CMD_STOP && cmd != CMD_RAW) {
            _car.stop();
            return;
        }

        switch (cmd) {
            case CMD_STOP:
                _car.stop();
                break;
            case CMD_FORWARD:
                _car.move_forward(speed);
                break;
            case CMD_BACKWARD:
                _car.move_backward(speed);
                break;
            case CMD_STRAFE_LEFT:
                _car.strafe_left(speed);
                break;
            case CMD_STRAFE_RIGHT:
                _car.strafe_right(speed);
                break;
            case CMD_DIAG_FL:
                _car.diag_forward_left(speed);
                break;
            case CMD_DIAG_FR:
                _car.diag_forward_right(speed);
                break;
            case CMD_DIAG_BL:
                _car.diag_backward_left(speed);
                break;
            case CMD_DIAG_BR:
                _car.diag_backward_right(speed);
                break;
            case CMD_SPIN_LEFT:
                _car.spin_left(speed);
                break;
            case CMD_SPIN_RIGHT:
                _car.spin_right(speed);
                break;
            case CMD_PIVOT_RIGHT:
                _car.pivot_right(speed);
                break;
            case CMD_PIVOT_REAR:
                _car.pivot_rear(speed);
                break;
            default:
                return;
        }

        send_ack(reply_port, cmd);
        log_command(cmd, speed, src);
    }
};
