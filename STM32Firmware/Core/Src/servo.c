#include "servo.h"

static uint32_t Servo_Angle_To_Pulse(int16_t angle)
{
    if (angle < 0) {
        angle = 0;
    } else if (angle > 180) {
        angle = 180;
    }

    return MIN_COUNTS
        + ((uint32_t)angle * (MAX_COUNTS - MIN_COUNTS)) / 180U;
}

void Set_Servo_Angle(TIM_HandleTypeDef* htim, uint32_t channel, int16_t angle)
{
    if (htim == NULL) {
        return;
    }

    __HAL_TIM_SET_COMPARE(htim, channel, Servo_Angle_To_Pulse(angle));
}
