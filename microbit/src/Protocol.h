#pragma once

#include <stdint.h>

// Binary protocol for MaixCam <-> micro:bit rover (115200 baud, P1=TX, P2=RX)
//
// Preset frame (4 bytes):
//   [0xAA] [CMD] [SPEED] [CHECKSUM]
//   CHECKSUM = (0xAA + CMD + SPEED) & 0xFF
//
// Raw mecanum frame (5 bytes):
//   [0xAA] [0x20] [WHEEL_DIRS] [SPEED] [CHECKSUM]
//   WHEEL_DIRS: 2 bits per wheel (UL, UR, LL, LR)
//     00 = stop, 01 = forward, 10 = backward, 11 = reserved/stop
//   CHECKSUM = (0xAA + 0x20 + WHEEL_DIRS + SPEED) & 0xFF
//
// Joystick frame (8 bytes):
//   [0xAA] [0x30] [X_LO] [X_HI] [Y_LO] [Y_HI] [MAX_SPEED] [CHECKSUM]
//   X/Y are signed int16 axes centered on 0, Xbox style range -32768..32767.
//   Y negative means forward, matching HID/gamepad screen coordinates.
//   CHECKSUM = sum(previous bytes) & 0xFF

static const uint8_t PROTO_SYNC = 0xAA;
static const uint8_t PROTO_ACK = 0x55;

static const uint8_t CMD_STOP = 0x00;
static const uint8_t CMD_FORWARD = 0x01;
static const uint8_t CMD_BACKWARD = 0x02;
static const uint8_t CMD_STRAFE_LEFT = 0x03;
static const uint8_t CMD_STRAFE_RIGHT = 0x04;
static const uint8_t CMD_DIAG_FL = 0x05;
static const uint8_t CMD_DIAG_FR = 0x06;
static const uint8_t CMD_DIAG_BL = 0x07;
static const uint8_t CMD_DIAG_BR = 0x08;
static const uint8_t CMD_SPIN_LEFT = 0x09;
static const uint8_t CMD_SPIN_RIGHT = 0x0A;
static const uint8_t CMD_PIVOT_RIGHT = 0x0B;
static const uint8_t CMD_PIVOT_REAR = 0x0C;
static const uint8_t CMD_RAW = 0x20;
static const uint8_t CMD_JOYSTICK = 0x30;

static const uint8_t WHEEL_DIR_STOP = 0x00;
static const uint8_t WHEEL_DIR_FORWARD = 0x01;
static const uint8_t WHEEL_DIR_BACKWARD = 0x02;

static const uint8_t DEFAULT_SPEED = 100;
static const uint8_t DEFAULT_JOYSTICK_DEADZONE_PERCENT = 12;

static inline uint8_t proto_checksum(uint8_t b0, uint8_t b1, uint8_t b2) {
    return (uint8_t)((b0 + b1 + b2) & 0xFF);
}

static inline uint8_t proto_checksum4(uint8_t b0, uint8_t b1, uint8_t b2, uint8_t b3) {
    return (uint8_t)((b0 + b1 + b2 + b3) & 0xFF);
}

static inline uint8_t wheel_dir_bits(uint8_t dirs, uint8_t shift) {
    return (dirs >> shift) & 0x03;
}
