#include "servo_fsm.h"

#include <stddef.h>

static bool PrepareOutput(ServoFsm *fsm, ServoFsmOutput *output)
{
    if (output == NULL)
    {
        return false;
    }

    output->angle_requested = false;
    output->angle = 0;
    output->cycle_completed = false;
    output->product_id = 0U;

    if (fsm == NULL)
    {
        return false;
    }

    return true;
}

static bool ConfigValid(const ServoFsmConfig *config)
{
    if (config == NULL)
    {
        return false;
    }

    if (config->rest_angle < 0 || config->rest_angle > 180)
    {
        return false;
    }
    if (config->deflect_angle < 0 || config->deflect_angle > 180)
    {
        return false;
    }
    if (config->rest_angle == config->deflect_angle)
    {
        return false;
    }

    /* Limit durations so deadlines remain comparable when the clock wraps. */
    if (config->deflect_ms == 0U || config->deflect_ms > INT32_MAX)
    {
        return false;
    }
    if (config->hold_ms == 0U || config->hold_ms > INT32_MAX)
    {
        return false;
    }
    if (config->return_ms == 0U || config->return_ms > INT32_MAX)
    {
        return false;
    }

    return true;
}

bool ServoFsm_Init(ServoFsm *fsm, const ServoFsmConfig *config,
                   uint32_t now_ms, ServoFsmOutput *output)
{
    if (!PrepareOutput(fsm, output))
    {
        return false;
    }
    if (!ConfigValid(config))
    {
        return false;
    }
    if (fsm->state != SERVO_FSM_UNINITIALIZED)
    {
        return false;
    }

    fsm->config = *config;
    fsm->product_id = 0U;
    fsm->cycle_active = false;

    /* First move to rest; Start is blocked until this return finishes. */
    fsm->state = SERVO_FSM_RETURNING;
    fsm->deadline_ms = now_ms + fsm->config.return_ms;
    output->angle_requested = true;
    output->angle = fsm->config.rest_angle;
    return true;
}

bool ServoFsm_Start(ServoFsm *fsm, uint32_t product_id,
                    uint32_t now_ms, ServoFsmOutput *output)
{
    if (!PrepareOutput(fsm, output))
    {
        return false;
    }
    if (fsm->state != SERVO_FSM_IDLE)
    {
        return false;
    }

    fsm->product_id = product_id;
    fsm->cycle_active = true;
    fsm->state = SERVO_FSM_DEFLECTING;
    fsm->deadline_ms = now_ms + fsm->config.deflect_ms;
    output->angle_requested = true;
    output->angle = fsm->config.deflect_angle;
    return true;
}

bool ServoFsm_Stop(ServoFsm *fsm, uint32_t now_ms, ServoFsmOutput *output)
{
    if (!PrepareOutput(fsm, output))
    {
        return false;
    }

    switch (fsm->state)
    {
        case SERVO_FSM_DEFLECTING:
        case SERVO_FSM_HOLDING:
            fsm->cycle_active = false;
            fsm->state = SERVO_FSM_RETURNING;
            fsm->deadline_ms = now_ms + fsm->config.return_ms;
            output->angle_requested = true;
            output->angle = fsm->config.rest_angle;
            return true;

        case SERVO_FSM_RETURNING:
        case SERVO_FSM_IDLE:
            /* Do not restart or shorten an existing return deadline. */
            fsm->cycle_active = false;
            return true;

        default:
            return false;
    }
}

bool ServoFsm_HandleTimeout(ServoFsm *fsm, uint32_t now_ms,
                            ServoFsmOutput *output)
{
    if (!PrepareOutput(fsm, output))
    {
        return false;
    }
    if (fsm->state != SERVO_FSM_DEFLECTING
        && fsm->state != SERVO_FSM_HOLDING
        && fsm->state != SERVO_FSM_RETURNING)
    {
        return false;
    }
    /* Unsigned subtraction handles clock wrap. A difference greater than
     * half the clock range means now_ms is still before the deadline.
     */
    const uint32_t elapsed_since_deadline = now_ms - fsm->deadline_ms;
    if (elapsed_since_deadline > INT32_MAX)
    {
        return false;
    }

    switch (fsm->state)
    {
        case SERVO_FSM_DEFLECTING:
            /* The outward motion has finished; keep the deflect angle. */
            fsm->state = SERVO_FSM_HOLDING;
            fsm->deadline_ms = now_ms + fsm->config.hold_ms;
            break;

        case SERVO_FSM_HOLDING:
            /* The hold has finished; command the rest angle. */
            fsm->state = SERVO_FSM_RETURNING;
            fsm->deadline_ms = now_ms + fsm->config.return_ms;
            output->angle_requested = true;
            output->angle = fsm->config.rest_angle;
            break;

        case SERVO_FSM_RETURNING:
            /* Report completion only for a cycle that was not cancelled. */
            fsm->state = SERVO_FSM_IDLE;
            if (fsm->cycle_active)
            {
                output->cycle_completed = true;
                output->product_id = fsm->product_id;
            }
            fsm->cycle_active = false;
            break;

        default:
            return false;
    }

    return true;
}
