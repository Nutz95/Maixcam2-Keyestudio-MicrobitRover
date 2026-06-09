#pragma once

#include <Arduino.h>
#include <Uart.h>

// External UART for MaixCam: P1 = TX, P2 = RX (edge connector pins 1 and 2)
#define ROVER_TX_PIN 1
#define ROVER_RX_PIN 2

extern Uart RoverSerial;

inline void rover_serial_begin(unsigned long baud) {
    RoverSerial.begin(baud);
}
