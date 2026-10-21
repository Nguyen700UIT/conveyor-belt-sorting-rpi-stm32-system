#ifndef UART_LINK_H
#define UART_LINK_H

#include "stm32f1xx_hal.h"

HAL_StatusTypeDef UartLink_Init(UART_HandleTypeDef *huart);
HAL_StatusTypeDef UartLink_SendText(const char* text);
HAL_StatusTypeDef UartLink_Service(void);
uint8_t UartLink_HasWork(void);
uint8_t UartLink_TakeByte(uint8_t *value);

#endif /* UART_LINK_H */