#pragma once

#include <Arduino.h>
#include <Stream.h>
#include "CommandDispatcher.h"
#include "Protocol.h"
#include "SerialSafe.h"

enum RxState {
    WAIT_SYNC,
    WAIT_CMD,
    WAIT_SPEED_OR_DIRS,
    WAIT_RAW_SPEED,
    WAIT_CHECKSUM,
    WAIT_RAW_CHECKSUM,
    WAIT_JOY_X_LO,
    WAIT_JOY_X_HI,
    WAIT_JOY_Y_LO,
    WAIT_JOY_Y_HI,
    WAIT_JOY_R_LO,
    WAIT_JOY_R_HI,
    WAIT_JOY_MAX_SPEED,
    WAIT_JOY_CHECKSUM,
};

struct RxContext {
    RxState state = WAIT_SYNC;
    uint8_t cmd = 0;
    uint8_t speed = 0;
    uint8_t dirs = 0;
    uint8_t joy_x_lo = 0;
    uint8_t joy_x_hi = 0;
    uint8_t joy_y_lo = 0;
    uint8_t joy_y_hi = 0;
    uint8_t joy_r_lo = 0;
    uint8_t joy_r_hi = 0;
};

class ProtocolHandler {
public:
    explicit ProtocolHandler(CommandDispatcher& dispatcher) : _dispatcher(dispatcher) {}

    void feed(RxContext& ctx, uint8_t byte, Stream& reply_port, const char* src = "?") {
        switch (ctx.state) {
            case WAIT_SYNC:
                if (byte == PROTO_SYNC) {
                    ctx.state = WAIT_CMD;
                }
                break;

            case WAIT_CMD:
                ctx.cmd = byte;
                ctx.state = ctx.cmd == CMD_JOYSTICK ? WAIT_JOY_X_LO : WAIT_SPEED_OR_DIRS;
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
                    if (_dispatcher.execute(ctx.cmd, ctx.speed)) {
                        send_ack(reply_port, ctx.cmd);
                        log_command(ctx.cmd, ctx.speed, src);
                    }
                }
                ctx.state = WAIT_SYNC;
                break;

            case WAIT_RAW_CHECKSUM:
                if (byte == proto_checksum4(PROTO_SYNC, CMD_RAW, ctx.dirs, ctx.speed)) {
                    _dispatcher.execute_raw(ctx.dirs, ctx.speed);
                    send_ack(reply_port, CMD_RAW);
                    log_command(CMD_RAW, ctx.speed, src);
                }
                ctx.state = WAIT_SYNC;
                break;

            case WAIT_JOY_X_LO:
                ctx.joy_x_lo = byte;
                ctx.state = WAIT_JOY_X_HI;
                break;

            case WAIT_JOY_X_HI:
                ctx.joy_x_hi = byte;
                ctx.state = WAIT_JOY_Y_LO;
                break;

            case WAIT_JOY_Y_LO:
                ctx.joy_y_lo = byte;
                ctx.state = WAIT_JOY_Y_HI;
                break;

            case WAIT_JOY_Y_HI:
                ctx.joy_y_hi = byte;
                ctx.state = WAIT_JOY_R_LO;
                break;

            case WAIT_JOY_R_LO:
                ctx.joy_r_lo = byte;
                ctx.state = WAIT_JOY_R_HI;
                break;

            case WAIT_JOY_R_HI:
                ctx.joy_r_hi = byte;
                ctx.state = WAIT_JOY_MAX_SPEED;
                break;

            case WAIT_JOY_MAX_SPEED:
                ctx.speed = byte;
                ctx.state = WAIT_JOY_CHECKSUM;
                break;

            case WAIT_JOY_CHECKSUM:
                if (byte == joystick_checksum(ctx)) {
                    _dispatcher.execute_joystick(
                        joystick_x(ctx), joystick_y(ctx), joystick_r(ctx), ctx.speed);
                    send_ack(reply_port, CMD_JOYSTICK);
                    log_command(CMD_JOYSTICK, ctx.speed, src);
                }
                ctx.state = WAIT_SYNC;
                break;
        }
    }

private:
    CommandDispatcher& _dispatcher;

    void send_ack(Stream& port, uint8_t cmd) {
        stream_write_byte(port, PROTO_ACK);
        stream_write_byte(port, cmd);
    }

    void log_command(uint8_t cmd, uint8_t speed, const char* src) {
        char line[72];
        snprintf(line, sizeof(line), "[rover] %s %s cmd=0x%02X spd=%u",
                 src, _dispatcher.command_name(cmd), cmd, speed);
        serial_usb_println(line);
    }

    uint8_t joystick_checksum(const RxContext& ctx) const {
        return static_cast<uint8_t>(
            (PROTO_SYNC + CMD_JOYSTICK + ctx.joy_x_lo + ctx.joy_x_hi +
             ctx.joy_y_lo + ctx.joy_y_hi + ctx.joy_r_lo + ctx.joy_r_hi +
             ctx.speed) & 0xFF);
    }

    int16_t joystick_x(const RxContext& ctx) const {
        return static_cast<int16_t>(
            static_cast<uint16_t>(ctx.joy_x_lo) |
            (static_cast<uint16_t>(ctx.joy_x_hi) << 8U));
    }

    int16_t joystick_y(const RxContext& ctx) const {
        return static_cast<int16_t>(
            static_cast<uint16_t>(ctx.joy_y_lo) |
            (static_cast<uint16_t>(ctx.joy_y_hi) << 8U));
    }

    int16_t joystick_r(const RxContext& ctx) const {
        return static_cast<int16_t>(
            static_cast<uint16_t>(ctx.joy_r_lo) |
            (static_cast<uint16_t>(ctx.joy_r_hi) << 8U));
    }
};
