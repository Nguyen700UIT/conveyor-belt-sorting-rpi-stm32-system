#include "uart_link.h"
#include <string.h>

static UART_HandleTypeDef *link_uart;
static uint8_t rx_byte;

static volatile uint8_t rx_recovery_needed;
static volatile uint8_t pending_byte;
static volatile uint8_t data_ready;

HAL_StatusTypeDef UartLink_Init(UART_HandleTypeDef *huart)
{
    if (huart == NULL) 
    {
        return HAL_ERROR;
    }

    link_uart = huart;
    data_ready = 0;
    rx_recovery_needed = 0;
    return HAL_UART_Receive_IT(link_uart, &rx_byte, 1U);
}

HAL_StatusTypeDef UartLink_SendText(const char* text)
{
    size_t length;

    if (link_uart == NULL || text == NULL) 
    {
        return HAL_ERROR;
    }

    length = strlen(text);

    if (length == 0U || length > UINT16_MAX) return HAL_ERROR;
    
    return HAL_UART_Transmit_IT(
        link_uart,
        (const uint8_t *)text,
        (uint16_t)length
    );
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (link_uart != huart) return;
    if (HAL_UART_GetError(huart) != HAL_UART_ERROR_NONE) return; //Return when error occured

    if (data_ready == 0U)
    {
        pending_byte = rx_byte;
        data_ready = 1U;
    }

    if (HAL_UART_Receive_IT(link_uart, &rx_byte, 1U) != HAL_OK)
    {
        HAL_UART_AbortReceive(huart);
        rx_recovery_needed = 1U;
    }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef* huart)
{
    if (huart != link_uart) return;

    HAL_UART_AbortReceive(huart);
    rx_recovery_needed = 1U;
}


uint8_t UartLink_TakeByte(uint8_t *value)
{
    uint32_t previous_mask;
    uint8_t available = 0U;

    if (value == NULL) 
    {
        return 0U;
    }

    previous_mask = __get_PRIMASK();
    __disable_irq();

    if (data_ready != 0U) //Data is ready to take
    {
        *value = pending_byte;
        data_ready = 0U;
        available = 1U;
    }

    __set_PRIMASK(previous_mask);

    return available;
}

HAL_StatusTypeDef UartLink_Service(void)
{
    if (link_uart == NULL) 
    {
        return HAL_ERROR;
    }

    if (rx_recovery_needed == 0U) 
    {
        return HAL_OK;
    }

    //Rx being used in callback
    rx_recovery_needed = 0U;
    data_ready = 0U;

    //Remove overrun flag
    __HAL_UART_CLEAR_OREFLAG(link_uart);

    return HAL_UART_Receive_IT(link_uart, &rx_byte, 1U);
}

uint8_t UartLink_HasWork(void)
{
    return (data_ready != 0U) || (rx_recovery_needed != 0U);
}