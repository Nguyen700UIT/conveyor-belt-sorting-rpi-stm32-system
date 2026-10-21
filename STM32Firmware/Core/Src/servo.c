#include "servo.h"

static uint32_t Servo_Angle_To_Pulse(int16_t angle)
{
    if (angle < 0) {
        angle = 0;
    } else if (angle > 180) {
        angle = 180;
    }

    return MIN_COUNTS
        + ((uint32_t)angle * (MAX_COUNTS - MIN_COUNTS) + 90U) / 180U;
}

void Set_Servo_Angle(TIM_HandleTypeDef* htim, uint32_t channel, int16_t angle)
{
    if (htim == NULL) {
        return;
    }

    __HAL_TIM_SET_COMPARE(htim, channel, Servo_Angle_To_Pulse(angle));
}

void Move_Servo_Angle_Smooth(TIM_HandleTypeDef* htim, uint32_t channel, int16_t angle)
{
    if (htim == NULL) {
        return;
    }

    const uint32_t target = Servo_Angle_To_Pulse(angle);
    uint32_t current = __HAL_TIM_GET_COMPARE(htim, channel);

    /* If no valid pulse is set yet, assume the servo starts at its center. */
    if (current < MIN_COUNTS || current > MAX_COUNTS) {
        current = Servo_Angle_To_Pulse(90);
        __HAL_TIM_SET_COMPARE(htim, channel, current);
    }

    while (current != target) {
        if (current < target) {
            current = (target - current > 5U) ? current + 5U : target;
        } else {
            current = (current - target > 5U) ? current - 5U : target;
        }

        __HAL_TIM_SET_COMPARE(htim, channel, current);
        HAL_Delay(20);
    }
}
