#include "uart_link.h"

#define UART_LINK_BUFFER_SIZE 64U

static UART_HandleTypeDef *link_uart;
static uint8_t rx_byte;
static uint8_t rx_buffer[UART_LINK_BUFFER_SIZE];
static uint8_t tx_buffer[UART_LINK_BUFFER_SIZE];

static volatile uint8_t rx_head;
static volatile uint8_t rx_tail;
static volatile uint8_t rx_overflow;
static volatile uint8_t rx_recovery_needed;

static volatile uint8_t tx_head;
static volatile uint8_t tx_tail;
static volatile uint8_t tx_count;
static volatile uint8_t tx_active;
static volatile uint8_t tx_recovery_needed;

bool UartLink_HasServices(void)
{
    return rx_head != rx_tail
        || rx_overflow != 0U
        || rx_recovery_needed != 0U
        || (tx_recovery_needed != 0U && tx_count != 0U);
}



static HAL_StatusTypeDef UartLink_StartTransmit(void)
{
    HAL_StatusTypeDef status;

    if (link_uart == NULL || tx_count == 0U)
    {
        tx_active = 0U;
        return HAL_OK;
    }

    tx_active = 1U;
    status = HAL_UART_Transmit_IT(link_uart, &tx_buffer[tx_head], 1U);
    if (status != HAL_OK)
    {
        tx_active = 0U;
        tx_recovery_needed = 1U;
    }

    return status;
}

HAL_StatusTypeDef UartLink_Init(UART_HandleTypeDef *huart)
{
    if (huart == NULL)
    {
        return HAL_ERROR;
    }

    link_uart = huart;
    rx_head = 0U;
    rx_tail = 0U;
    rx_overflow = 0U;
    rx_recovery_needed = 0U;
    tx_head = 0U;
    tx_tail = 0U;
    tx_count = 0U;
    tx_active = 0U;
    tx_recovery_needed = 0U;

    return HAL_UART_Receive_IT(link_uart, &rx_byte, 1U);
}

HAL_StatusTypeDef UartLink_Send(const uint8_t *data, uint16_t length)
{
    uint32_t previous_mask;
    uint16_t index;

    if (link_uart == NULL || data == NULL || length == 0U)
    {
        return HAL_ERROR;
    }

    previous_mask = __get_PRIMASK();
    __disable_irq();

    if ((uint16_t)tx_count + length > UART_LINK_BUFFER_SIZE)
    {
        __set_PRIMASK(previous_mask);
        return HAL_BUSY;
    }

    for (index = 0U; index < length; index++)
    {
        tx_buffer[tx_tail] = data[index];
        tx_tail = (uint8_t)((tx_tail + 1U) % UART_LINK_BUFFER_SIZE);
        tx_count++;
    }

    if (tx_active == 0U)
    {
        (void)UartLink_StartTransmit();
    }

    __set_PRIMASK(previous_mask);
    return HAL_OK;
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    uint8_t next_head;

    if (link_uart != huart)
    {
        return;
    }

    if (HAL_UART_GetError(huart) == HAL_UART_ERROR_NONE)
    {
        next_head = (uint8_t)((rx_head + 1U) % UART_LINK_BUFFER_SIZE);
        if (next_head != rx_tail)
        {
            rx_buffer[rx_head] = rx_byte;
            rx_head = next_head;
        }
        else
        {
            rx_overflow = 1U;
        }
    }

    if (HAL_UART_Receive_IT(link_uart, &rx_byte, 1U) != HAL_OK)
    {
        HAL_UART_AbortReceive(huart);
        rx_recovery_needed = 1U;
    }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    if (link_uart != huart)
    {
        return;
    }

    HAL_UART_AbortReceive(huart);
    rx_recovery_needed = 1U;
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if (link_uart != huart)
    {
        return;
    }

    if (tx_count != 0U)
    {
        tx_head = (uint8_t)((tx_head + 1U) % UART_LINK_BUFFER_SIZE);
        tx_count--;
    }

    if (tx_count == 0U)
    {
        tx_active = 0U;
    }
    else if (UartLink_StartTransmit() != HAL_OK)
    {
        tx_recovery_needed = 1U;
    }
}

uint16_t UartLink_Read(uint8_t *data, uint16_t max_length)
{
    uint32_t previous_mask;
    uint16_t length = 0U;

    if (data == NULL || max_length == 0U)
    {
        return 0U;
    }

    previous_mask = __get_PRIMASK();
    __disable_irq();

    while (length < max_length && rx_tail != rx_head)
    {
        data[length] = rx_buffer[rx_tail];
        rx_tail = (uint8_t)((rx_tail + 1U) % UART_LINK_BUFFER_SIZE);
        length++;
    }

    __set_PRIMASK(previous_mask);
    return length;
}

uint8_t UartLink_RxOverflowed(void)
{
    uint32_t previous_mask = __get_PRIMASK();
    uint8_t overflowed;

    __disable_irq();
    overflowed = rx_overflow;
    rx_overflow = 0U;
    __set_PRIMASK(previous_mask);

    return overflowed;
}

HAL_StatusTypeDef UartLink_Service(void)
{
    HAL_StatusTypeDef status = HAL_OK;
    uint32_t previous_mask;

    if (link_uart == NULL)
    {
        return HAL_ERROR;
    }

    if (rx_recovery_needed != 0U)
    {
        rx_recovery_needed = 0U;
        __HAL_UART_CLEAR_OREFLAG(link_uart);
        status = HAL_UART_Receive_IT(link_uart, &rx_byte, 1U);
        if (status != HAL_OK)
        {
            rx_recovery_needed = 1U;
            return status;
        }
    }

    if (tx_recovery_needed != 0U && tx_count != 0U)
    {
        previous_mask = __get_PRIMASK();
        __disable_irq();
        tx_recovery_needed = 0U;
        status = UartLink_StartTransmit();
        __set_PRIMASK(previous_mask);
    }

    return status;
}
