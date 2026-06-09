#pragma once

#include <Arduino.h>
#include <Stream.h>

// UARTE0 (Serial USB bridge via KL27) : TX peut bloquer avec Uart::write().
// Ecriture non-bloquante pour eviter de figer setup()/loop().

inline bool serial_usb_write_byte(uint8_t data) {
    NRF_UART0->TXD = data;
    uint32_t start = millis();
    while (!NRF_UART0->EVENTS_TXDRDY) {
        if (millis() - start > 5) {
            return false;
        }
    }
    NRF_UART0->EVENTS_TXDRDY = 0;
    return true;
}

inline void serial_usb_println(const char* msg) {
    while (*msg) {
        if (!serial_usb_write_byte((uint8_t)*msg)) {
            return;
        }
        msg++;
    }
    serial_usb_write_byte('\r');
    serial_usb_write_byte('\n');
}

inline void stream_write_byte(Stream& port, uint8_t data) {
    if (&port == &Serial) {
        serial_usb_write_byte(data);
    } else {
        port.write(data);
    }
}
