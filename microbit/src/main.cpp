#include <Arduino.h>
#include "CommandDispatcher.h"
#include "MotorDriver.h"
#include "Protocol.h"
#include "ProtocolParser.h"
#include "SerialRover.h"
#include "SerialSafe.h"

MecanumCarDriver car;
CommandDispatcher dispatcher(car);
ProtocolHandler protocol(dispatcher);

static UartIncomingFrame usb_incoming_frame;
static UartIncomingFrame rover_incoming_frame;

void setup() {
    Serial.begin(115200);
    rover_serial_begin(115200);
    delay(100);

    serial_usb_println("[rover] boot");
    car.begin();

    serial_usb_println("[rover] ready p1p2+usb 115200");
}

void loop() {
    while (Serial.available() > 0) {
        protocol.feed_byte(usb_incoming_frame, (uint8_t)Serial.read(), Serial, "usb");
    }

    while (RoverSerial.available() > 0) {
        protocol.feed_byte(rover_incoming_frame, (uint8_t)RoverSerial.read(), RoverSerial, "p1p2");
    }
}
