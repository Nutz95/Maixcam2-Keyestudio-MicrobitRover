#pragma once

#include <Arduino.h>
#include <Stream.h>
#include "CommandDispatcher.h"
#include "Protocol.h"
#include "SerialSafe.h"

/** Etat du parseur UART : quel octet de la trame on attend. */
enum UartParserState {
    WAIT_SYNC_BYTE,
    WAIT_COMMAND_BYTE,
    WAIT_PRESET_SPEED_OR_WHEEL_DIRS,
    WAIT_RAW_WHEEL_SPEED,
    WAIT_PRESET_CHECKSUM,
    WAIT_RAW_CHECKSUM,
    WAIT_STRAFE_LOW_BYTE,
    WAIT_STRAFE_HIGH_BYTE,
    WAIT_FORWARD_LOW_BYTE,
    WAIT_FORWARD_HIGH_BYTE,
    WAIT_SPIN_LOW_BYTE,
    WAIT_SPIN_HIGH_BYTE,
    WAIT_PIVOT_LOW_BYTE,
    WAIT_PIVOT_HIGH_BYTE,
    WAIT_JOYSTICK_MAX_SPEED,
    WAIT_JOYSTICK_CHECKSUM,
};

/** Octets deja recus pour la trame en cours de reception. */
struct UartIncomingFrame {
    UartParserState parser_state = WAIT_SYNC_BYTE;
    uint8_t command_byte = 0;
    uint8_t motor_speed = 0;
    uint8_t wheel_direction_bits = 0;
    uint8_t strafe_byte_low = 0;
    uint8_t strafe_byte_high = 0;
    uint8_t forward_byte_low = 0;
    uint8_t forward_byte_high = 0;
    uint8_t spin_byte_low = 0;
    uint8_t spin_byte_high = 0;
    uint8_t pivot_byte_low = 0;
    uint8_t pivot_byte_high = 0;
};

class ProtocolHandler {
public:
    explicit ProtocolHandler(CommandDispatcher& dispatcher) : _dispatcher(dispatcher) {}

    void feed_byte(UartIncomingFrame& incoming, uint8_t byte, Stream& reply_port, const char* source = "?") {
        switch (incoming.parser_state) {
            case WAIT_SYNC_BYTE:
                if (byte == PROTO_SYNC) {
                    incoming.parser_state = WAIT_COMMAND_BYTE;
                }
                break;

            case WAIT_COMMAND_BYTE:
                incoming.command_byte = byte;
                incoming.parser_state = incoming.command_byte == CMD_JOYSTICK
                    ? WAIT_STRAFE_LOW_BYTE
                    : WAIT_PRESET_SPEED_OR_WHEEL_DIRS;
                break;

            case WAIT_PRESET_SPEED_OR_WHEEL_DIRS:
                if (incoming.command_byte == CMD_RAW) {
                    incoming.wheel_direction_bits = byte;
                    incoming.parser_state = WAIT_RAW_WHEEL_SPEED;
                } else {
                    incoming.motor_speed = byte;
                    incoming.parser_state = WAIT_PRESET_CHECKSUM;
                }
                break;

            case WAIT_RAW_WHEEL_SPEED:
                incoming.motor_speed = byte;
                incoming.parser_state = WAIT_RAW_CHECKSUM;
                break;

            case WAIT_PRESET_CHECKSUM:
                if (byte == proto_checksum(PROTO_SYNC, incoming.command_byte, incoming.motor_speed)) {
                    if (_dispatcher.execute(incoming.command_byte, incoming.motor_speed)) {
                        send_ack(reply_port, incoming.command_byte);
                        log_command(incoming.command_byte, incoming.motor_speed, source);
                    }
                }
                incoming.parser_state = WAIT_SYNC_BYTE;
                break;

            case WAIT_RAW_CHECKSUM:
                if (byte == proto_checksum4(
                        PROTO_SYNC, CMD_RAW, incoming.wheel_direction_bits, incoming.motor_speed)) {
                    _dispatcher.execute_raw(incoming.wheel_direction_bits, incoming.motor_speed);
                    send_ack(reply_port, CMD_RAW);
                    log_command(CMD_RAW, incoming.motor_speed, source);
                }
                incoming.parser_state = WAIT_SYNC_BYTE;
                break;

            case WAIT_STRAFE_LOW_BYTE:
                incoming.strafe_byte_low = byte;
                incoming.parser_state = WAIT_STRAFE_HIGH_BYTE;
                break;

            case WAIT_STRAFE_HIGH_BYTE:
                incoming.strafe_byte_high = byte;
                incoming.parser_state = WAIT_FORWARD_LOW_BYTE;
                break;

            case WAIT_FORWARD_LOW_BYTE:
                incoming.forward_byte_low = byte;
                incoming.parser_state = WAIT_FORWARD_HIGH_BYTE;
                break;

            case WAIT_FORWARD_HIGH_BYTE:
                incoming.forward_byte_high = byte;
                incoming.parser_state = WAIT_SPIN_LOW_BYTE;
                break;

            case WAIT_SPIN_LOW_BYTE:
                incoming.spin_byte_low = byte;
                incoming.parser_state = WAIT_SPIN_HIGH_BYTE;
                break;

            case WAIT_SPIN_HIGH_BYTE:
                incoming.spin_byte_high = byte;
                incoming.parser_state = WAIT_PIVOT_LOW_BYTE;
                break;

            case WAIT_PIVOT_LOW_BYTE:
                incoming.pivot_byte_low = byte;
                incoming.parser_state = WAIT_PIVOT_HIGH_BYTE;
                break;

            case WAIT_PIVOT_HIGH_BYTE:
                incoming.pivot_byte_high = byte;
                incoming.parser_state = WAIT_JOYSTICK_MAX_SPEED;
                break;

            case WAIT_JOYSTICK_MAX_SPEED:
                incoming.motor_speed = byte;
                incoming.parser_state = WAIT_JOYSTICK_CHECKSUM;
                break;

            case WAIT_JOYSTICK_CHECKSUM:
                if (byte == joystick_frame_checksum(incoming)) {
                    _dispatcher.execute_joystick(
                        decode_strafe_axis(incoming),
                        decode_forward_axis(incoming),
                        decode_spin_axis(incoming),
                        decode_pivot_axis(incoming),
                        incoming.motor_speed);
                    send_ack(reply_port, CMD_JOYSTICK);
                    log_command(CMD_JOYSTICK, incoming.motor_speed, source);
                }
                incoming.parser_state = WAIT_SYNC_BYTE;
                break;
        }
    }

private:
    CommandDispatcher& _dispatcher;

    void send_ack(Stream& port, uint8_t command_byte) {
        stream_write_byte(port, PROTO_ACK);
        stream_write_byte(port, command_byte);
    }

    void log_command(uint8_t command_byte, uint8_t speed, const char* source) {
        char line[72];
        snprintf(line, sizeof(line), "[rover] %s %s cmd=0x%02X spd=%u",
                 source, _dispatcher.command_name(command_byte), command_byte, speed);
        serial_usb_println(line);
    }

    uint8_t joystick_frame_checksum(const UartIncomingFrame& incoming) const {
        return static_cast<uint8_t>(
            (PROTO_SYNC + CMD_JOYSTICK
             + incoming.strafe_byte_low + incoming.strafe_byte_high
             + incoming.forward_byte_low + incoming.forward_byte_high
             + incoming.spin_byte_low + incoming.spin_byte_high
             + incoming.pivot_byte_low + incoming.pivot_byte_high
             + incoming.motor_speed) & 0xFF);
    }

    static int16_t decode_signed_axis(uint8_t byte_low, uint8_t byte_high) {
        return static_cast<int16_t>(
            static_cast<uint16_t>(byte_low) |
            (static_cast<uint16_t>(byte_high) << 8U));
    }

    int16_t decode_strafe_axis(const UartIncomingFrame& incoming) const {
        return decode_signed_axis(incoming.strafe_byte_low, incoming.strafe_byte_high);
    }

    int16_t decode_forward_axis(const UartIncomingFrame& incoming) const {
        return decode_signed_axis(incoming.forward_byte_low, incoming.forward_byte_high);
    }

    int16_t decode_spin_axis(const UartIncomingFrame& incoming) const {
        return decode_signed_axis(incoming.spin_byte_low, incoming.spin_byte_high);
    }

    int16_t decode_pivot_axis(const UartIncomingFrame& incoming) const {
        return decode_signed_axis(incoming.pivot_byte_low, incoming.pivot_byte_high);
    }
};
