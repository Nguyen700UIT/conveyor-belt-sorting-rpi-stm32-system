#ifndef UART_PROTOCOL_H
#define UART_PROTOCOL_H

#include "stm32f1xx_hal.h"

typedef enum
{
    UART_PROTOCOL_CMD_PING = 0x01U,
    UART_PROTOCOL_CMD_UNRIPE = 0x02U,
    UART_PROTOCOL_CMD_RIPE = 0x03U,
    UART_PROTOCOL_CMD_SPOILED = 0x04U,
    UART_PROTOCOL_CMD_START = 0x05U
} UartProtocol_Command_t;

typedef enum
{
    UART_PROTOCOL_STATUS_PONG = 0x00U,
    UART_PROTOCOL_STATUS_ACK = 0x01U,
    UART_PROTOCOL_STATUS_FULL = 0x02U,
    UART_PROTOCOL_STATUS_NOT_READY = 0x03U,
    UART_PROTOCOL_STATUS_BAD_CMD = 0x04U
} UartProtocol_Status_t;

/* The application/FSM handler is called only for a new, valid command. */
typedef UartProtocol_Status_t (*UartProtocol_CommandHandler_t)(uint8_t command);

void UartProtocol_Init(UartProtocol_CommandHandler_t command_handler);
HAL_StatusTypeDef UartProtocol_Process(void);

#endif /* UART_PROTOCOL_H */
