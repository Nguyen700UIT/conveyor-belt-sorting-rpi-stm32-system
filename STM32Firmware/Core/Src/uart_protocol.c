#include "uart_protocol.h"

#include <string.h>

#include "uart_link.h"

#define UART_PROTOCOL_REQUEST_SOF 0xA5U
#define UART_PROTOCOL_RESPONSE_SOF 0x5AU
#define UART_PROTOCOL_FRAME_SIZE 4U
#define UART_PROTOCOL_CRC_POLYNOMIAL 0x07U
#define UART_PROTOCOL_READ_CHUNK_SIZE 16U

static uint8_t request_frame[UART_PROTOCOL_FRAME_SIZE];
static uint8_t request_length;
static UartProtocol_CommandHandler_t command_handler;
static uint8_t has_last_accepted;
static uint8_t last_accepted_sequence;
static uint8_t last_accepted_command;

static uint8_t UartProtocol_Crc8(const uint8_t *data, uint8_t length)
{
    uint8_t crc = 0U;
    uint8_t index;
    uint8_t bit;

    for (index = 0U; index < length; index++)
    {
        crc ^= data[index];
        for (bit = 0U; bit < 8U; bit++)
        {
            if ((crc & 0x80U) != 0U)
            {
                crc = (uint8_t)((crc << 1U) ^ UART_PROTOCOL_CRC_POLYNOMIAL);
            }
            else
            {
                crc <<= 1U;
            }
        }
    }

    return crc;
}

static uint8_t UartProtocol_IsCommandValid(uint8_t command)
{
    return (uint8_t)(command >= UART_PROTOCOL_CMD_PING &&
                     command <= UART_PROTOCOL_CMD_START);
}

static HAL_StatusTypeDef UartProtocol_SendResponse(uint8_t sequence,
                                                   UartProtocol_Status_t status)
{
    uint8_t response[UART_PROTOCOL_FRAME_SIZE];

    response[0] = UART_PROTOCOL_RESPONSE_SOF;
    response[1] = sequence;
    response[2] = (uint8_t)status;
    response[3] = UartProtocol_Crc8(response, UART_PROTOCOL_FRAME_SIZE - 1U);

    return UartLink_Send(response, UART_PROTOCOL_FRAME_SIZE);
}

static HAL_StatusTypeDef UartProtocol_HandleFrame(const uint8_t *frame)
{
    uint8_t sequence = frame[1];
    uint8_t command = frame[2];
    UartProtocol_Status_t status;

    if (UartProtocol_Crc8(frame, UART_PROTOCOL_FRAME_SIZE - 1U) != frame[3])
    {
        return HAL_OK;
    }

    if (UartProtocol_IsCommandValid(command) == 0U)
    {
        return UartProtocol_SendResponse(sequence, UART_PROTOCOL_STATUS_BAD_CMD);
    }

    if (command == UART_PROTOCOL_CMD_PING)
    {
        return UartProtocol_SendResponse(sequence, UART_PROTOCOL_STATUS_PONG);
    }

    if (has_last_accepted != 0U && sequence == last_accepted_sequence)
    {
        if (command == last_accepted_command)
        {
            return UartProtocol_SendResponse(sequence, UART_PROTOCOL_STATUS_ACK);
        }

        return UartProtocol_SendResponse(sequence, UART_PROTOCOL_STATUS_BAD_CMD);
    }

    if (command_handler == NULL)
    {
        return UartProtocol_SendResponse(sequence, UART_PROTOCOL_STATUS_NOT_READY);
    }

    status = command_handler(command);
    if (status != UART_PROTOCOL_STATUS_ACK &&
        status != UART_PROTOCOL_STATUS_FULL &&
        status != UART_PROTOCOL_STATUS_NOT_READY)
    {
        status = UART_PROTOCOL_STATUS_BAD_CMD;
    }

    if (status == UART_PROTOCOL_STATUS_ACK)
    {
        /* Store acceptance before sending: an ACK lost on TX must not enqueue again. */
        has_last_accepted = 1U;
        last_accepted_sequence = sequence;
        last_accepted_command = command;
    }

    return UartProtocol_SendResponse(sequence, status);
}

static HAL_StatusTypeDef UartProtocol_ConsumeByte(uint8_t byte)
{
    HAL_StatusTypeDef status;

    if (request_length == 0U)
    {
        if (byte != UART_PROTOCOL_REQUEST_SOF)
        {
            return HAL_OK;
        }
        request_frame[request_length++] = byte;
        return HAL_OK;
    }

    request_frame[request_length++] = byte;
    if (request_length < UART_PROTOCOL_FRAME_SIZE)
    {
        return HAL_OK;
    }

    status = UartProtocol_HandleFrame(request_frame);

    /* On a malformed frame, retain a later SOF byte for resynchronization. */
    if (UartProtocol_Crc8(request_frame, UART_PROTOCOL_FRAME_SIZE - 1U) != request_frame[3])
    {
        uint8_t index;
        for (index = 1U; index < UART_PROTOCOL_FRAME_SIZE; index++)
        {
            if (request_frame[index] == UART_PROTOCOL_REQUEST_SOF)
            {
                uint8_t remaining = (uint8_t)(UART_PROTOCOL_FRAME_SIZE - index);
                memmove(request_frame, &request_frame[index], remaining);
                request_length = remaining;
                return status;
            }
        }
    }

    request_length = 0U;
    return status;
}

void UartProtocol_Init(UartProtocol_CommandHandler_t handler)
{
    command_handler = handler;
    request_length = 0U;
    has_last_accepted = 0U;
    last_accepted_sequence = 0U;
    last_accepted_command = 0U;
}

HAL_StatusTypeDef UartProtocol_Process(void)
{
    uint8_t input[UART_PROTOCOL_READ_CHUNK_SIZE];
    uint16_t count;
    uint16_t index;
    HAL_StatusTypeDef status;

    status = UartLink_Service();
    if (status != HAL_OK)
    {
        return status;
    }

    if (UartLink_RxOverflowed() != 0U)
    {
        request_length = 0U;
    }

    do
    {
        count = UartLink_Read(input, sizeof(input));
        for (index = 0U; index < count; index++)
        {
            status = UartProtocol_ConsumeByte(input[index]);
            if (status != HAL_OK)
            {
                return status;
            }
        }
    } while (count == sizeof(input));

    return HAL_OK;
}
