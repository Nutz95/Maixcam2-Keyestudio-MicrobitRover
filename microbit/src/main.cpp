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

static RxContext usb_ctx;
static RxContext rover_ctx;

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
        protocol.feed(usb_ctx, (uint8_t)Serial.read(), Serial, "usb");
    }

    while (RoverSerial.available() > 0) {
        protocol.feed(rover_ctx, (uint8_t)RoverSerial.read(), RoverSerial, "p1p2");
    }
}
