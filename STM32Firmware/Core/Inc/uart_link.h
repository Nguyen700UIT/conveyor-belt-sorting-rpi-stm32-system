#ifndef UART_LINK_H
#define UART_LINK_H

#include "stm32f1xx_hal.h"

HAL_StatusTypeDef UartLink_Init(UART_HandleTypeDef *huart);
HAL_StatusTypeDef UartLink_Send(const uint8_t *data, uint16_t length);
uint16_t UartLink_Read(uint8_t *data, uint16_t max_length);
uint8_t UartLink_RxOverflowed(void);
HAL_StatusTypeDef UartLink_Service(void);

#endif /* UART_LINK_H */
