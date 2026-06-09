#include "SerialRover.h"

Uart RoverSerial(reinterpret_cast<NRF_UART_Type *>(NRF_UARTE1),
                 UARTE1_IRQn, ROVER_RX_PIN, ROVER_TX_PIN);

#if defined(NRF52_SERIES)
extern "C" void UARTE1_IRQHandler(void) {
    RoverSerial.IrqHandler();
}
#endif
